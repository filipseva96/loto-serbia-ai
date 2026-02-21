"""
Configuration for Loto Serbia AI - v3.0
"""
import os
import logging
from pathlib import Path
from math import comb

# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None
IS_STREAMLIT_CLOUD = os.getenv("STREAMLIT_SHARING_MODE") is not None or \
                     os.getenv("STREAMLIT_RUNTIME_ENVIRONMENT") == "cloud"
IS_CLOUD = IS_RAILWAY or IS_STREAMLIT_CLOUD

# ============================================================================
# PATHS
# ============================================================================
if IS_CLOUD:
    BASE_DIR = Path("/mount/src/loto-serbia-ai") if IS_STREAMLIT_CLOUD else Path("/app")
    DATA_DIR = BASE_DIR / "data"
else:
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "loto_serbia.db"

# ============================================================================
# LOTTERY CONFIGURATION - SERBIA LOTO 7/39
# ============================================================================
MIN_NUMBER = 1
MAX_NUMBER = 39
NUMBERS_PER_DRAW = 7
NUMBER_RANGE = (MIN_NUMBER, MAX_NUMBER)
VALID_NUMBERS = list(range(MIN_NUMBER, MAX_NUMBER + 1))
HAS_BONUS = False
BONUS_MIN = None
BONUS_MAX = None
BONUS_RANGE = None

DRAW_DAYS = [0, 2, 3]  # Monday, Wednesday, Thursday
DRAW_HOUR = 21
DRAW_MINUTE = 0
DRAW_TIMEZONE = "Europe/Belgrade"

GAME_NAME = "Loto 7/39"
GAME_COUNTRY = "Serbia"
GAME_ID = 1
DRAWS_PER_WEEK = 3

# ============================================================================
# PRIZE TABLE (RSD)
# ============================================================================
PRIZE_TABLE = {
    7: 10_000_000,
    6: 100_000,
    5: 1_500,
    4: 50,
    3: 20
}
TICKET_COST = 100

# ============================================================================
# MATHEMATICAL CONSTANTS
# ============================================================================
TOTAL_COMBINATIONS = comb(MAX_NUMBER, NUMBERS_PER_DRAW)  # 15,380,937

# Pre-calculate expected value for logging
def _calc_ev():
    ev = 0.0
    for k, prize in PRIZE_TABLE.items():
        remaining = MAX_NUMBER - NUMBERS_PER_DRAW
        needed = NUMBERS_PER_DRAW - k
        if needed < 0 or needed > remaining:
            continue
        p = (comb(NUMBERS_PER_DRAW, k) * comb(remaining, needed)) / TOTAL_COMBINATIONS
        ev += p * prize
    return ev

_EXPECTED_VALUE = _calc_ev()

# ============================================================================
# SCRAPING
# ============================================================================
BASE_URL = "https://lutrija.rs/Results/OfficialReports?gameNo=1"
SCRAPING_ENABLED = not IS_STREAMLIT_CLOUD
SCRAPE_INTERVAL_HOURS = 24
MAX_RETRIES = 3
TIMEOUT_SECONDS = 20

# ============================================================================
# PORTFOLIO
# ============================================================================
DEFAULT_TICKETS = 10
MAX_TICKETS = 50
MIN_DRAWS_FOR_ANALYSIS = 50
LOOKBACK_WINDOW = 20
COVERAGE_MONTE_CARLO_SAMPLES = 1500
WHEEL_GUARANTEE_DEFAULT = 3

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = logging.DEBUG if not IS_CLOUD else logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("lotto_ai.config")

logger.info(f"Environment: Cloud={IS_CLOUD}, Railway={IS_RAILWAY}, Streamlit={IS_STREAMLIT_CLOUD}")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Database path: {DB_PATH}")
logger.info(f"Number range: {NUMBER_RANGE}")
logger.info(f"Total combinations: {TOTAL_COMBINATIONS:,}")
logger.info(f"Expected value per ticket: {_EXPECTED_VALUE:.2f} RSD")
logger.info(f"Draw days: {DRAW_DAYS}")
logger.info(f"Has bonus number: {HAS_BONUS}")
if not SCRAPING_ENABLED:
    logger.warning("Scraping is DISABLED (Cloud environment)")