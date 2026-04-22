"""
Market-cap enrichment service for risk-factor groups.

This used to live on `EquityRiskFactorGroup.update_market_caps()`, mixing
JSON file I/O, YFinance API calls, and bucket categorization on a class
nominally responsible for "loading a JSON file." Now it's a standalone
service that takes a `RiskFactorGroup`, looks up market caps via an
injectable ticker factory (so tests don't have to monkeypatch yfinance),
and writes the categories back into the group's config.
"""

from typing import Callable, Optional

from .base_group import RiskFactorGroup
from ...utils.logging import get_logger

logger = get_logger(__name__)


# Market-cap thresholds in USD. Anything above 200B is mega; 10B–200B large;
# 2B–10B mid; below 2B small. Uses inclusive lower bound (so a stock with
# exactly $200B is still 'large' to leave headroom for movement).
MEGA_CAP_THRESHOLD = 200_000_000_000
LARGE_CAP_THRESHOLD = 10_000_000_000
MID_CAP_THRESHOLD = 2_000_000_000


def categorize_market_cap(market_cap: Optional[float]) -> str:
    """Return one of 'mega', 'large', 'mid', 'small'.

    `None` input is treated as 'small' so callers don't need a separate
    branch when an enrichment failed; the per-symbol failure path in
    `MarketCapEnricher.enrich` writes 'unknown' explicitly.
    """
    if market_cap is None:
        return "small"
    if market_cap > MEGA_CAP_THRESHOLD:
        return "mega"
    if market_cap > LARGE_CAP_THRESHOLD:
        return "large"
    if market_cap > MID_CAP_THRESHOLD:
        return "mid"
    return "small"


def _default_ticker_factory(symbol: str):
    """Return a YFinance Ticker for `symbol`. Imported lazily so the test
    suite can run without yfinance installed and the module stays cheap to
    import."""
    import yfinance as yf  # noqa: WPS433 — intentional lazy import

    return yf.Ticker(symbol)


# Keep a top-level reference to the yfinance module so tests can patch
# `finbase.data.risk_factor_groups.market_cap_enricher.yf` cleanly.
try:
    import yfinance as yf  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — yfinance is a hard dep in the env
    yf = None  # type: ignore[assignment]


class MarketCapEnricher:
    """Decorate every risk factor in a group with market-cap metadata."""

    def __init__(
        self,
        ticker_factory: Optional[Callable[[str], object]] = None,
    ):
        if ticker_factory is None:
            self._ticker_factory: Callable[[str], object] = self._default_factory
        else:
            self._ticker_factory = ticker_factory

    @staticmethod
    def _default_factory(symbol: str):
        return yf.Ticker(symbol)

    def enrich(self, group: RiskFactorGroup, save_every: Optional[int] = None) -> int:
        """Look up market caps for every risk factor in `group`.

        Args:
            group: The group to mutate in place.
            save_every: When set, persist the group via `group.save()`
                after every N successful enrichments. Useful for resuming
                long jobs without losing progress on rate-limit errors.

        Returns:
            Count of risk factors successfully enriched.
        """
        success = 0
        total = group.count()
        for i, rf in enumerate(group.config["risk_factors"], start=1):
            symbol = rf["symbol"]
            try:
                ticker = self._ticker_factory(symbol)
                info = ticker.info
                market_cap = info.get("marketCap", 0) or 0

                rf["market_cap"] = market_cap
                rf["market_cap_category"] = categorize_market_cap(market_cap)
                success += 1

                if i % 10 == 0 or i == total:
                    logger.info(f"Market cap progress: {i}/{total}")

                if save_every and i % save_every == 0:
                    group.save()

            except Exception as e:
                logger.warning(f"Failed to fetch market cap for {symbol}: {e}")
                rf["market_cap"] = None
                rf["market_cap_category"] = "unknown"

        return success
