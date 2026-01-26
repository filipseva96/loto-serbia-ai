"""
Draw scraping module - NO auto-execution
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil.rrule import rrule, WEEKLY, TU, FR
from lotto_ai.config import BASE_URL, SCRAPING_ENABLED, logger
from lotto_ai.core.db import get_session, Draw

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def generate_draw_dates(start_date, end_date):
    """Generate all Tuesday & Friday dates between two dates"""
    rules = rrule(
        WEEKLY,
        byweekday=(TU, FR),
        dtstart=start_date,
        until=end_date
    )
    return [d.date() for d in rules]

def fetch_draw(date):
    """Fetch a single draw from the website"""
    if not SCRAPING_ENABLED:
        logger.warning("Scraping is disabled in this environment")
        return None
    
    url = f"{BASE_URL}?date={date.isoformat()}"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            logger.warning(f"Failed to fetch {date}: HTTP {r.status_code}")
            return None
        
        soup = BeautifulSoup(r.text, "html.parser")
        numbers = soup.select(
            "#lqZoneOutputOutilsResultats span.num:not(.complementaire)"
        )
        bonus = soup.select_one(
            "#lqZoneOutputOutilsResultats span.num.complementaire"
        )
        
        if len(numbers) < 7 or bonus is None:
            logger.warning(f"No valid draw found for {date}")
            return None
        
        main_numbers = sorted(int(n.text.strip()) for n in numbers[:7])
        bonus_number = int(bonus.text.strip())
        
        return {
            'draw_date': date.isoformat(),
            'n1': main_numbers[0],
            'n2': main_numbers[1],
            'n3': main_numbers[2],
            'n4': main_numbers[3],
            'n5': main_numbers[4],
            'n6': main_numbers[5],
            'n7': main_numbers[6],
            'bonus': bonus_number
        }
    except Exception as e:
        logger.error(f"Error fetching draw {date}: {e}")
        return None

def insert_draw(draw_data):
    """Insert draw into database using SQLAlchemy"""
    session = get_session()
    try:
        # Check if exists
        existing = session.query(Draw).filter_by(draw_date=draw_data['draw_date']).first()
        if existing:
            logger.info(f"Draw {draw_data['draw_date']} already exists")
            return False
        
        # Insert new
        draw = Draw(**draw_data)
        session.add(draw)
        session.commit()
        logger.info(f"Inserted draw {draw_data['draw_date']}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting draw: {e}")
        return False
    finally:
        session.close()

def scrape_recent_draws(days_back=30):
    """
    Scrape recent draws (safe for cloud execution)
    
    Args:
        days_back: Number of days to look back
    """
    if not SCRAPING_ENABLED:
        logger.warning("Scraping disabled - skipping")
        return 0
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days_back)
    
    draw_dates = generate_draw_dates(start_date, end_date)
    logger.info(f"Checking {len(draw_dates)} potential draw dates")
    
    inserted_count = 0
    for date in draw_dates:
        draw_data = fetch_draw(date)
        if draw_data:
            if insert_draw(draw_data):
                inserted_count += 1
    
    logger.info(f"Scraping complete: {inserted_count} new draws inserted")
    return inserted_count

def scrape_all_draws():
    """Scrape full history (LOCAL ONLY - DO NOT USE IN CLOUD)"""
    if not SCRAPING_ENABLED:
        logger.error("Cannot scrape in cloud environment")
        return 0
    
    start_date = datetime(2009, 1, 1)
    end_date = datetime.today()
    
    draw_dates = generate_draw_dates(start_date, end_date)
    logger.info(f"Scraping full history: {len(draw_dates)} draws")
    
    inserted_count = 0
    for date in draw_dates:
        draw_data = fetch_draw(date)
        if draw_data:
            if insert_draw(draw_data):
                inserted_count += 1
    
    logger.info(f"Full scrape complete: {inserted_count} new draws")
    return inserted_count

# DO NOT auto-execute - must be called explicitly
if __name__ == "__main__":
    # Only for manual testing
    logger.info("Manual scrape triggered")
    scrape_recent_draws(days_back=7)