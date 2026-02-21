"""
Configuration for Loto Serbia AI
"""
from pathlib import Path
import os
import logging

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment detection
IS_CLOUD = os.getenv("CLOUD_ENV", "0") == "1"
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None
IS_STREAMLIT = os.getenv("STREAMLIT_RUNTIME") is not None

# Base directories
if IS_RAILWAY:
    BASE_DIR = Path("/app/data")
elif IS_STREAMLIT or IS_CLOUD:
    BASE_DIR = Path("/tmp")
else:
    BASE_DIR = Path(__file__).resolve().parent.parent / "data"

BASE_DIR.mkdir(parents=True, exist_ok=True)

# Database path
DB_PATH = BASE_DIR / "loto_serbia.db"

# Models directory
MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ⚠️ SERBIA-SPECIFIC CONFIGURATION
SCRAPING_ENABLED = True  # Always enabled (PDF parsing)
BASE_URL = "https://lutrija.rs/Results/OfficialReports?gameNo=1"

# Game parameters
NUMBER_RANGE = (1, 39)  # ✅ Changed from (1, 50)
NUMBERS_PER_DRAW = 7
HAS_BONUS = False  # ✅ No bonus number

# Draw schedule (Serbia: Tue/Thu/Fri)
DRAW_DAYS = [1, 3, 4]  # Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4
DRAW_HOUR = 21  # 9:00 PM

logger.info(f"Environment: Cloud={IS_CLOUD}, Railway={IS_RAILWAY}, Streamlit={IS_STREAMLIT}")
logger.info(f"Data directory: {BASE_DIR}")
logger.info(f"Database path: {DB_PATH}")
logger.info(f"Number range: {NUMBER_RANGE}")
logger.info(f"Draw days: {DRAW_DAYS}")