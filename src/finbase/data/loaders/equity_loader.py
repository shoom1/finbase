"""Equity data loader using YFinance with rate limiting."""

import yfinance as yf
import pandas as pd
import time
from typing import Callable, List, Optional
from datetime import datetime

from ..database.timeseries_db import TimeSeriesDB, DatabaseError, ValidationError
from ..risk_factor_groups import RiskFactorGroup
from ...utils.logging import get_logger
from ...config import get_settings

# Initialize logger
logger = get_logger(__name__)


class LoaderError(Exception):
    """Base exception for data loader errors."""
    pass


class EquityLoader:
    """Loader for equity data from YFinance with rate limiting."""

    def __init__(
        self,
        db: TimeSeriesDB,
        delay_seconds: Optional[float] = None,
        batch_size: Optional[int] = None,
        batch_pause: Optional[float] = None,
        ticker_factory: Optional[Callable[[str], object]] = None,
    ):
        """
        Initialize equity loader with rate limiting.

        Any rate-limit argument left as ``None`` is resolved from
        ``Settings.rate_limit`` at construction time, so values flow from
        ``~/.finbaserc`` or ``FINBASE_YFINANCE_*`` env vars without the
        caller having to know they exist.

        Args:
            db: TimeSeriesDB instance
            delay_seconds: Delay between each symbol request. Defaults to
                ``settings.rate_limit.yfinance_delay_seconds`` (5s).
            batch_size: Number of symbols before a longer pause. Defaults
                to ``settings.rate_limit.yfinance_batch_size`` (10).
            batch_pause: Additional pause after each batch. Defaults to
                ``settings.rate_limit.yfinance_batch_pause`` (30s).
            ticker_factory: Callable ``f(symbol) -> ticker`` returning an
                object with a ``history(start, end, auto_adjust)`` method
                (the yfinance ``Ticker`` contract). Defaults to
                ``yfinance.Ticker`` but is injectable so tests and
                alternate data sources don't need to monkeypatch globals.
                Mirrors ``MarketCapEnricher.ticker_factory``.

        Raises:
            LoaderError: If validation fails
        """
        if not isinstance(db, TimeSeriesDB):
            raise LoaderError("db must be a TimeSeriesDB instance")

        rate_limit = get_settings().rate_limit
        if delay_seconds is None:
            delay_seconds = rate_limit.yfinance_delay_seconds
        if batch_size is None:
            batch_size = rate_limit.yfinance_batch_size
        if batch_pause is None:
            batch_pause = rate_limit.yfinance_batch_pause

        if delay_seconds < 0:
            raise LoaderError("delay_seconds must be non-negative")

        if batch_size <= 0:
            raise LoaderError("batch_size must be positive")

        if batch_pause < 0:
            raise LoaderError("batch_pause must be non-negative")

        self.db = db
        self.delay_seconds = delay_seconds
        self.batch_size = batch_size
        self.batch_pause = batch_pause
        self._ticker_factory = ticker_factory
        self.request_count = 0

    def _make_ticker(self, symbol: str):
        """Resolve the ticker object for ``symbol``.

        Read at call time (not constructor time) so tests that
        monkeypatch ``equity_loader.yf`` after instance creation still
        take effect — the historical contract this module exposes.
        """
        if self._ticker_factory is not None:
            return self._ticker_factory(symbol)
        return yf.Ticker(symbol)

    def _has_existing_data(self, symbol: str, data_source: str = 'yfinance') -> bool:
        """
        Check if symbol already has data in the database.

        Args:
            symbol: Ticker symbol
            data_source: Data source (default: 'yfinance')

        Returns:
            True if symbol exists and has timeseries data, False otherwise
        """
        try:
            # Check if risk factor exists and has data
            rf_info = self.db.get_risk_factor_info(symbol, data_source)
            if rf_info is None:
                return False

            # Check if it has any timeseries data by looking at the risk_factor table
            # If start_date exists, it means data has been loaded
            if rf_info.get('start_date') and rf_info.get('end_date'):
                return True

            return False

        except Exception as e:
            logger.warning(f"Error checking existing data for {symbol}: {e}")
            return False

    def load_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        asset_subclass: str = 'stock',
        description: Optional[str] = None,
        country: str = 'US',
        currency: str = 'USD',
        sector: Optional[str] = None,
        metadata: Optional[dict] = None,
        max_retries: int = 3,
        skip_existing: bool = True
    ) -> int:
        """
        Load data for a single symbol with error handling and retries.

        Args:
            symbol: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            asset_subclass: 'stock' or 'index'
            description: Company/index description
            country: Country code
            currency: Currency code
            sector: Sector (for stocks)
            metadata: Additional metadata
            max_retries: Maximum number of retry attempts on failure
            skip_existing: If True, skip symbols that already have data (default: True)

        Returns:
            Number of records loaded (0 if skipped)

        Raises:
            LoaderError: If data loading fails after all retries
            ValidationError: If input validation fails
        """
        # Validate inputs
        if not symbol or not isinstance(symbol, str):
            raise ValidationError("Symbol must be a non-empty string")

        if not start_date or not end_date:
            raise ValidationError("Start date and end date are required")

        # Validate date format
        try:
            pd.to_datetime(start_date)
            pd.to_datetime(end_date)
        except Exception as e:
            raise ValidationError(f"Invalid date format (use YYYY-MM-DD): {e}")

        # Check if symbol already has data
        if skip_existing and self._has_existing_data(symbol):
            logger.info(f"Skipping {symbol} - data already exists")
            return 0

        logger.info(f"Loading {symbol}...")

        # Rate limiting: Add delay between requests
        if self.request_count > 0:
            time.sleep(self.delay_seconds)

        # Additional pause every batch_size requests
        if self.request_count > 0 and self.request_count % self.batch_size == 0:
            logger.info(f"Rate limit: Batch pause for {self.batch_pause:.0f}s after {self.batch_size} requests")
            time.sleep(self.batch_pause)

        # Download data from YFinance with retry logic
        last_error = None
        for attempt in range(max_retries):
            try:
                ticker = self._make_ticker(symbol)
                df = ticker.history(start=start_date, end=end_date, auto_adjust=False)
                self.request_count += 1

                if df.empty:
                    logger.warning(f"No data available for {symbol}")
                    return 0

                # Validate downloaded data
                if not isinstance(df, pd.DataFrame):
                    raise LoaderError(f"YFinance returned invalid data type for {symbol}")

                # Add risk factor to database
                try:
                    risk_factor_id = self.db.add_risk_factor(
                        symbol=symbol,
                        asset_class='equity',
                        asset_subclass=asset_subclass,
                        description=description or symbol,
                        currency=currency,
                        country=country,
                        sector=sector,
                        data_source='yfinance',
                        frequency='daily',
                        metadata=metadata
                    )
                except (DatabaseError, ValidationError) as e:
                    raise LoaderError(f"Failed to add risk factor for {symbol}: {e}")

                # Prepare DataFrame for insertion
                # YFinance returns: Open, High, Low, Close, Volume, Dividends, Stock Splits
                # Map to our schema (use .values to avoid index mismatch)
                df_clean = pd.DataFrame()
                df_clean['date'] = df.index.values
                df_clean['open'] = df['Open'].values
                df_clean['high'] = df['High'].values
                df_clean['low'] = df['Low'].values
                df_clean['close'] = df['Close'].values
                df_clean['adj_close'] = df['Adj Close'].values if 'Adj Close' in df.columns else df['Close'].values
                df_clean['volume'] = df['Volume'].values

                # Add to database
                try:
                    records_added = self.db.add_timeseries_data(
                        risk_factor_id=risk_factor_id,
                        data=df_clean,
                        date_column='date',
                        close_column='close',
                        adj_close_column='adj_close',
                        open_column='open',
                        high_column='high',
                        low_column='low',
                        volume_column='volume'
                    )

                    logger.info(f"Loaded {records_added} records for {symbol}")
                    return records_added

                except (DatabaseError, ValidationError) as e:
                    raise LoaderError(f"Failed to add timeseries data for {symbol}: {e}")

            except (LoaderError, ValidationError):
                # Don't retry on validation errors
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}")
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error loading {symbol} after {max_retries} attempts: {e}")

        # If we get here, all retries failed
        if last_error:
            raise LoaderError(f"Failed to load {symbol} after {max_retries} attempts: {last_error}")

        return 0

    def load_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        asset_subclass: str = 'stock',
        sector: Optional[str] = None,
        max_symbols: Optional[int] = None,
        skip_existing: bool = True
    ) -> int:
        """
        Load data for multiple symbols with rate limiting.

        Args:
            symbols: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            asset_subclass: 'stock' or 'index'
            sector: Sector (optional, applies to all)
            max_symbols: Maximum number of symbols to load (for testing/limiting)
            skip_existing: If True, skip symbols that already have data (default: True)

        Returns:
            Total number of records loaded
        """
        # Limit symbols if requested
        symbols_to_load = symbols[:max_symbols] if max_symbols else symbols

        logger.info(f"Loading {len(symbols_to_load)} symbols (delay: {self.delay_seconds}s, batch size: {self.batch_size})")
        if max_symbols and len(symbols) > max_symbols:
            logger.info(f"  (Limited from {len(symbols)} total symbols)")

        total_records = 0
        start_time = time.time()

        for i, symbol in enumerate(symbols_to_load, 1):
            records = self.load_symbol(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                asset_subclass=asset_subclass,
                sector=sector,
                skip_existing=skip_existing
            )
            total_records += records

            # Progress update every 10 symbols
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = len(symbols_to_load) - i
                eta = remaining / rate if rate > 0 else 0
                logger.info(f"  Progress: {i}/{len(symbols_to_load)} ({i/len(symbols_to_load)*100:.1f}%) - ETA: {eta/60:.1f} min")

        elapsed = time.time() - start_time
        logger.info(f"Total: {total_records} records loaded for {len(symbols_to_load)} symbols in {elapsed/60:.1f} minutes")
        return total_records

    def load_from_group(
        self,
        group: RiskFactorGroup,
        start_date: str,
        end_date: str,
        max_symbols: Optional[int] = None,
        skip_existing: bool = True
    ) -> int:
        """
        Load data for all risk factors in a group with rate limiting.

        Args:
            group: RiskFactorGroup instance
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            max_symbols: Maximum number of symbols to load (for testing/limiting)
            skip_existing: If True, skip symbols that already have data (default: True)

        Returns:
            Total number of records loaded
        """
        metadata = group.get_metadata()
        total_count = group.count()

        # Limit if requested
        risk_factors_to_load = group.config['risk_factors'][:max_symbols] if max_symbols else group.config['risk_factors']

        logger.info(f"Loading group: {metadata['group_name']} ({len(risk_factors_to_load)} risk factors)")
        logger.info(f"  Rate limiting: {self.delay_seconds}s delay, pause every {self.batch_size} symbols")
        if max_symbols and total_count > max_symbols:
            logger.info(f"  (Limited from {total_count} total risk factors)")

        total_records = 0
        start_time = time.time()

        for i, rf_data in enumerate(risk_factors_to_load, 1):
            records = self.load_symbol(
                symbol=rf_data['symbol'],
                start_date=start_date,
                end_date=end_date,
                asset_subclass=metadata.get('asset_subclass', 'stock'),
                description=rf_data.get('description'),
                country=rf_data.get('country', 'US'),
                currency=rf_data.get('currency', 'USD'),
                sector=rf_data.get('sector'),
                metadata=rf_data.get('metadata'),
                skip_existing=skip_existing
            )
            total_records += records

            # Progress update every 5 symbols
            if i % 5 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = len(risk_factors_to_load) - i
                eta = remaining / rate if rate > 0 else 0
                logger.info(f"  Progress: {i}/{len(risk_factors_to_load)} ({i/len(risk_factors_to_load)*100:.1f}%) - ETA: {eta/60:.1f} min")

        elapsed = time.time() - start_time
        logger.info(f"Group '{metadata['group_name']}': {total_records} records loaded in {elapsed/60:.1f} minutes")
        return total_records
