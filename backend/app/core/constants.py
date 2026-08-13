"""
Application-wide constants.

This module is the single source of truth for every magic number and string
in the application. No constant should ever be hardcoded in business logic,
client code, or route handlers.

Constants defined here serve as compile-time defaults. Runtime-configurable
values live in config.py and reference these defaults where appropriate.
"""

# ── Risk Levels ──────────────────────────────────────────────────────────────

RISK_HIGH: str = "high"
RISK_MEDIUM: str = "medium"
RISK_LOW: str = "low"

# ── Risk Thresholds ──────────────────────────────────────────────────────────

HIGH_RISK_THRESHOLD: int = 3   # ≥3 overlapping files → HIGH
MEDIUM_RISK_THRESHOLD: int = 2  # 2 overlapping files  → MEDIUM
                                # 1 overlapping file   → LOW (implicit)

# ── GitHub API ───────────────────────────────────────────────────────────────

GITHUB_API_BASE_URL: str = "https://api.github.com"
GITHUB_PER_PAGE: int = 100         # Max items per page (GitHub maximum)
GITHUB_DEFAULT_TIMEOUT: int = 30   # Seconds per request
GITHUB_MAX_RETRIES: int = 3

# ── Pagination ───────────────────────────────────────────────────────────────

MAX_PRS_TO_ANALYZE: int = 100  # Cap for MVP — single page fetch

# ── Concurrency ──────────────────────────────────────────────────────────────

MAX_CONCURRENT_REQUESTS: int = 10  # asyncio.Semaphore limit

# ── Cache ────────────────────────────────────────────────────────────────────

DEFAULT_CACHE_TTL_SECONDS: int = 300   # 5 minutes
DEFAULT_CACHE_MAX_ENTRIES: int = 100

# ── URL Pattern ──────────────────────────────────────────────────────────────

GITHUB_PR_URL_PATTERN: str = (
    r"^https://github\.com/"
    r"(?P<owner>[a-zA-Z0-9\-\.]+)/"
    r"(?P<repo>[a-zA-Z0-9\-\.\_]+)/"
    r"pull/"
    r"(?P<number>\d+)"
    r"/?$"
)

# ── Application ──────────────────────────────────────────────────────────────

APP_NAME: str = "PRInsight"
APP_VERSION: str = "0.1.0"
