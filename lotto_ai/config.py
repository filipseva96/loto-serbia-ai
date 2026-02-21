"""
Configuration for Loto Serbia AI
"""
import os
import logging
from pathlib import Path

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
    # Cloud: use /tmp or mounted volume
    BASE_DIR = Path("/mount/src/loto-serbia-ai") if IS_STREAMLIT_CLOUD else Path("/app")
    DATA_DIR = BASE_DIR / "data"
else:
    # Local: use project directory
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "loto_serbia.db"

# ============================================================================
# LOTTERY CONFIGURATION - SERBIA LOTO 7/39
# ============================================================================
MIN_NUMBER = 1
MAX_NUMBER = 39
NUMBERS_PER_DRAW = 7

# Number range tuple (for compatibility)
NUMBER_RANGE = (MIN_NUMBER, MAX_NUMBER)

# All valid numbers (for validation)
VALID_NUMBERS = list(range(MIN_NUMBER, MAX_NUMBER + 1))

# Serbia Loto 7/39 does NOT have a bonus number
HAS_BONUS = False
BONUS_MIN = None
BONUS_MAX = None
BONUS_RANGE = None

# Draw days (Monday=0, Tuesday=1, ..., Sunday=6)
# Serbia Loto 7/39 draws on: Monday, Wednesday, Thursday
DRAW_DAYS = [0, 2, 3]

# Draw timing (Serbia time - CET/CEST)
DRAW_HOUR = 21  # 9 PM
DRAW_MINUTE = 0
DRAW_TIMEZONE = "Europe/Belgrade"

# Game info
GAME_NAME = "Loto 7/39"
GAME_COUNTRY = "Serbia"
GAME_ID = 1  # lutrija.rs gameNo parameter

# Draw frequency
DRAWS_PER_WEEK = 3

# ============================================================================
# SCRAPING CONFIGURATION
# ============================================================================
BASE_URL = "https://lutrija.rs/Results/OfficialReports?gameNo=1"
SCRAPING_ENABLED = not IS_STREAMLIT_CLOUD  # Disable scraping on Streamlit Cloud

# Scraping schedule (for automated updates)
SCRAPE_INTERVAL_HOURS = 24  # Check for new draws daily
MAX_RETRIES = 3
TIMEOUT_SECONDS = 20

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================
# Feature engineering
LOOKBACK_WINDOW = 20  # Analyze last 20 draws for patterns
MIN_DRAWS_FOR_TRAINING = 50  # Minimum draws needed to train model

# Portfolio generation
DEFAULT_TICKETS = 10
MAX_TICKETS = 50
USE_ADAPTIVE_DEFAULT = True

# Model parameters
RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

# ============================================================================
# UI CONFIGURATION
# ============================================================================
APP_TITLE = "🇷🇸 Loto Serbia AI Predictor"
APP_ICON = "🎰"

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = logging.DEBUG if not IS_CLOUD else logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configure logger
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("lotto_ai.config")

# Log environment info
logger.info(f"Environment: Cloud={IS_CLOUD}, Railway={IS_RAILWAY}, Streamlit={IS_STREAMLIT_CLOUD}")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Database path: {DB_PATH}")
logger.info(f"Number range: {NUMBER_RANGE}")
logger.info(f"Draw days: {DRAW_DAYS}")
logger.info(f"Draw time: {DRAW_HOUR:02d}:{DRAW_MINUTE:02d} {DRAW_TIMEZONE}")
logger.info(f"Has bonus number: {HAS_BONUS}")
if not SCRAPING_ENABLED:
    logger.warning("Scraping is DISABLED (Cloud environment)")