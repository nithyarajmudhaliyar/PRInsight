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

# ── GitHub OAuth ─────────────────────────────────────────────────────────────

GITHUB_OAUTH_AUTHORIZE_URL: str = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL: str = "https://github.com/login/oauth/access_token"
GITHUB_OAUTH_USER_URL: str = "https://api.github.com/user"

# ── Session ──────────────────────────────────────────────────────────────────

SESSION_COOKIE_NAME: str = "prinsight_session"
OAUTH_STATE_COOKIE_NAME: str = "prinsight_oauth_state"
DEFAULT_SESSION_TTL_SECONDS: int = 86400  # 24 hours
OAUTH_STATE_TTL_SECONDS: int = 600         # 10 minutes

# ── Rate Limiting ────────────────────────────────────────────────────────────

DEFAULT_RATE_LIMIT_ANON_MAX: int = 10       # Requests per window (anonymous)
DEFAULT_RATE_LIMIT_ANON_WINDOW: int = 60    # Window in seconds (1 minute)
DEFAULT_RATE_LIMIT_AUTH_MAX: int = 30       # Requests per window (authenticated)
DEFAULT_RATE_LIMIT_AUTH_WINDOW: int = 60    # Window in seconds (1 minute)
