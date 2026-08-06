from enum import StrEnum


class Frequency(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class CashflowType(StrEnum):
    contribution = "contribution"
    withdrawal = "withdrawal"


class CashflowTiming(StrEnum):
    beginning = "beginning"
    end = "end"


class RebalanceMode(StrEnum):
    none = "none"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    threshold = "threshold"


class DataSource(StrEnum):
    sec_open_data = "sec_open_data"


class PriceField(StrEnum):
    nav_per_unit = "nav_per_unit"


class AlignmentFrequency(StrEnum):
    monthly = "monthly"
    daily = "daily"


class ErrorCode(StrEnum):
    """Stable machine-readable codes, paired with the existing human-readable
    `detail` message, so a deployer's monitoring/alerting can branch on error
    type without parsing free-text strings."""

    UNSUPPORTED_DATA_SOURCE = "UNSUPPORTED_DATA_SOURCE"
    NAV_CACHE_MISSING = "NAV_CACHE_MISSING"
    FUND_UNIVERSE_CACHE_MISSING = "FUND_UNIVERSE_CACHE_MISSING"
    INSUFFICIENT_NAV_HISTORY = "INSUFFICIENT_NAV_HISTORY"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
