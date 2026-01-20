import requests
import sqlite3
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil.rrule import rrule, WEEKLY, TU, FR

from lotto_ai.config import DB_PATH
BASE_URL = "https://loteries.lotoquebec.com/en/lotteries/lotto-max-resultats"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# -----------------------------
# Date utilities
# -----------------------------
def generate_draw_dates(start_date, end_date):
    """Generate all Tuesday & Friday dates between two dates"""
    rules = rrule(
        WEEKLY,
        byweekday=(TU, FR),
        dtstart=start_date,
        until=end_date
    )
    return [d.date() for d in rules]

# -----------------------------
# Scraping logic
# -----------------------------
def fetch_draw(date):
    url = f"{BASE_URL}?date={date.isoformat()}"
    r = requests.get(url, headers=HEADERS, timeout=10)

    if r.status_code != 200:
        print(f"⚠️ Failed to fetch {date}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    numbers = soup.select(
        "#lqZoneOutputOutilsResultats "
        "span.num:not(.complementaire)"
    )

    bonus = soup.select_one(
        "#lqZoneOutputOutilsResultats span.num.complementaire"
    )

    if len(numbers) < 7 or bonus is None:
        print(f"⚠️ No valid draw found for {date}")
        return None

    main_numbers = sorted(int(n.text.strip()) for n in numbers[:7])
    bonus_number = int(bonus.text.strip())

    return (date.isoformat(), *main_numbers, bonus_number)

# -----------------------------
# Database insertion
# -----------------------------
def insert_draw(draw):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("""
        INSERT INTO draws
        (draw_date, n1, n2, n3, n4, n5, n6, n7, bonus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, draw)
        conn.commit()
        print(f"✅ Inserted draw {draw[0]}")
    except sqlite3.IntegrityError:
        print(f"⏭️ Draw {draw[0]} already exists")
    finally:
        conn.close()

def ensure_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS draws (
        draw_date TEXT PRIMARY KEY,
        n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, n6 INTEGER, n7 INTEGER,
        bonus INTEGER
    )
    """)
    conn.commit()
    conn.close()


# -----------------------------
# Main runner
# -----------------------------
def main():
    # Adjust if you want full history
    ensure_table()
    start_date = datetime(2026, 1, 1)
    end_date = datetime.today()

    draw_dates = generate_draw_dates(start_date, end_date)

    print(f"🔎 Fetching {len(draw_dates)} draw dates...")

    for d in draw_dates:
        draw = fetch_draw(d)
        if draw:
            insert_draw(draw)

if __name__ == "__main__":
    main()