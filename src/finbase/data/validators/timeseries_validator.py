"""
Time series data validation module.

Validates financial time series data for:
- Sufficient data points
- Missing dates detection
- Price anomalies and outliers
- OHLC consistency
- Corporate action adjustments
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List
from ...config import get_settings
from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Results from time series validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of validation results."""
        lines = [f"Validation: {'PASSED' if self.is_valid else 'FAILED'}"]

        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if self.info:
            lines.append(f"\nInfo:")
            for key, value in self.info.items():
                lines.append(f"  - {key}: {value}")

        return "\n".join(lines)


class TimeSeriesValidator:
    """Validator for financial time series data quality."""

    def __init__(self):
        """Initialize validator with configuration settings."""
        self.config = get_settings().validation

    def validate(self, df: pd.DataFrame, symbol: str) -> ValidationResult:
        """
        Validate time series data quality.

        Args:
            df: DataFrame with OHLCV data (date as index)
            symbol: Symbol being validated

        Returns:
            ValidationResult with errors, warnings, and info
        """
        errors = []
        warnings = []
        info = {}

        # Ensure date is index
        if 'date' in df.columns:
            df = df.set_index('date')

        df.index = pd.to_datetime(df.index)

        # 1. Check minimum data points
        data_count = len(df)
        info['data_points'] = data_count

        if data_count < self.config.min_data_points:
            warnings.append(
                f"Only {data_count} data points (expected > {self.config.min_data_points})"
            )

        # 2. Check for missing business days
        if data_count > 0:
            date_range = pd.date_range(df.index.min(), df.index.max(), freq='B')
            missing_dates = date_range.difference(df.index)
            missing_pct = len(missing_dates) / len(date_range) if len(date_range) > 0 else 0

            info['missing_business_days'] = len(missing_dates)
            info['missing_percentage'] = f"{missing_pct * 100:.1f}%"

            if missing_pct > self.config.max_missing_pct:
                warnings.append(
                    f"{len(missing_dates)} missing business days ({missing_pct*100:.1f}% > {self.config.max_missing_pct*100:.1f}% threshold)"
                )

        # 3. Check for zero/negative prices
        if 'close' in df.columns:
            invalid_prices = (df['close'] <= 0) | df['close'].isna()
            if invalid_prices.any():
                errors.append(
                    f"Invalid prices (zero, negative, or NaN): {invalid_prices.sum()} occurrences"
                )

        # 4. Check for extreme price movements
        if 'close' in df.columns and len(df) > 1:
            returns = df['close'].pct_change()
            extreme_returns = returns[returns.abs() > self.config.max_single_day_return]

            if len(extreme_returns) > 0:
                max_return = extreme_returns.abs().max()
                warnings.append(
                    f"Extreme price movements detected: {len(extreme_returns)} days with |return| > {self.config.max_single_day_return*100:.0f}% (max: {max_return*100:.1f}%)"
                )

        # 5. Check OHLC consistency
        if self.config.validate_ohlc and all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            inconsistent = (
                (df['high'] < df['low']) |
                (df['close'] > df['high']) |
                (df['close'] < df['low']) |
                (df['open'] > df['high']) |
                (df['open'] < df['low'])
            )

            if inconsistent.any():
                errors.append(
                    f"OHLC data inconsistency: {inconsistent.sum()} occurrences"
                )

        # 6. Check for outliers using standard deviation
        if 'close' in df.columns and len(df) > 2:
            z_scores = np.abs((df['close'] - df['close'].mean()) / df['close'].std())
            outliers = z_scores > self.config.outlier_std_threshold

            if outliers.any():
                info['outliers_detected'] = outliers.sum()
                warnings.append(
                    f"{outliers.sum()} potential outliers detected (>{self.config.outlier_std_threshold} std devs)"
                )

        # 7. Check for data gaps
        if len(df) > 1:
            df_sorted = df.sort_index()
            time_diffs = df_sorted.index.to_series().diff()

            # Find gaps > 10 business days
            large_gaps = time_diffs[time_diffs > pd.Timedelta(days=14)]  # ~10 business days
            if len(large_gaps) > 0:
                info['large_gaps'] = len(large_gaps)
                warnings.append(
                    f"{len(large_gaps)} large time gaps detected (>10 business days)"
                )

        # 8. Check volume data if available
        if 'volume' in df.columns:
            zero_volume = df['volume'] == 0
            if zero_volume.any():
                info['zero_volume_days'] = zero_volume.sum()
                if zero_volume.sum() / len(df) > 0.05:  # > 5% of days
                    warnings.append(
                        f"{zero_volume.sum()} days with zero volume ({zero_volume.sum()/len(df)*100:.1f}% of data)"
                    )

        # Log validation results
        is_valid = len(errors) == 0

        if not is_valid:
            logger.error(f"Validation failed for {symbol}: {len(errors)} errors")
        elif warnings:
            logger.warning(f"Validation passed with warnings for {symbol}: {len(warnings)} warnings")
        else:
            logger.info(f"Validation passed for {symbol}")

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            info=info
        )

    def validate_or_raise(self, df: pd.DataFrame, symbol: str):
        """
        Validate data and raise exception if validation fails.

        Args:
            df: DataFrame with OHLCV data
            symbol: Symbol being validated

        Raises:
            ValueError: If validation fails
        """
        result = self.validate(df, symbol)

        if not result.is_valid:
            raise ValueError(f"Validation failed for {symbol}:\n{result}")

        if result.warnings:
            logger.warning(f"Data quality warnings for {symbol}:\n{result}")
