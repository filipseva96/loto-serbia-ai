"""
Loto Serbia scraper - ENHANCED VERSION
Handles multiple PDF formats (Службени, Privremeni, etc.)
Fixed: round_number is now saved to database
"""
import requests
import re
import io
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from PyPDF2 import PdfReader

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from lotto_ai.config import BASE_URL, logger, NUMBER_RANGE
from lotto_ai.core.db import get_session, Draw

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def extract_js_data():
    """Extract officialReportsTableData from JavaScript"""
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()

        match = re.search(
            r'var officialReportsTableData = (\[.*?\]);',
            response.text,
            re.DOTALL
        )

        if not match:
            logger.error("Could not find officialReportsTableData in page")
            return []

        import json
        data = json.loads(match.group(1))
        logger.info(f"Found {len(data)} official reports")
        return data

    except Exception as e:
        logger.error(f"Error extracting JS data: {e}")
        return []


def extract_numbers_from_pdf(pdf_url):
    """
    Download PDF and extract winning numbers
    ENHANCED v6: Saves round_number, validates against NUMBER_RANGE
    """
    try:
        full_url = f"https://lutrija.rs{pdf_url}"
        logger.debug(f"Downloading PDF: {full_url}")

        response = requests.get(full_url, headers=HEADERS, timeout=20)
        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)

        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        # Extract round number
        round_match = re.search(
            r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)',
            pdf_url, re.IGNORECASE
        )
        if not round_match:
            round_match = re.search(
                r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)',
                text, re.IGNORECASE
            )

        round_number = int(round_match.group(1)) if round_match else None

        if round_number is None:
            logger.warning(f"Could not extract round number from: {pdf_url}")
            return None

        # Extract date
        draw_date = None
        filename_date_patterns = [
            r'(\d{2})\.(\d{2})\.(\d{4})',
            r'(\d{2})-(\d{2})-(\d{4})',
            r'од\s+(\d{2})\.(\d{2})\.(\d{4})',
        ]

        for pattern in filename_date_patterns:
            date_match = re.search(pattern, pdf_url)
            if date_match:
                day, month, year = date_match.groups()
                draw_date = f"{year}-{month}-{day}"
                break

        if not draw_date:
            content_date_patterns = [
                r'од\s+(\d{2})\.(\d{2})\.(\d{4})',
                r'JOKER\s+од\s+(\d{2})\.(\d{2})\.(\d{4})',
                r'brojeva\s+i\s+JOKER\s+од\s+(\d{2})\.(\d{2})\.(\d{4})',
                r'(\d{2})\.(\d{2})\.(\d{4})\.',
            ]

            for pattern in content_date_patterns:
                date_match = re.search(pattern, text[:500], re.IGNORECASE)
                if date_match:
                    day, month, year = date_match.groups()
                    draw_date = f"{year}-{month}-{day}"
                    break

        if not draw_date:
            logger.warning(f"Could not extract date: {pdf_url}")
            return None

        min_num, max_num = NUMBER_RANGE

        # STAGE 1: HIGH-CONFIDENCE PATTERNS
        high_confidence_patterns = [
            (r'ЛОТ\s*О\s*7\s*О\s*Д\s*39[^\n]*\n[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', 1),
            (r'Dobitna\s+kombinacija\s+Loto\s+7/39[^\d]*\([^\)]+\)\s+(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', 2),
            (r'\([^\)]+\)\s+(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', 3),
        ]

        for pattern, pattern_id in high_confidence_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL))
            for match in matches:
                try:
                    candidate_numbers = [int(match.group(i)) for i in range(1, 8)]
                    if (all(min_num <= n <= max_num for n in candidate_numbers) and
                            len(set(candidate_numbers)) == 7 and
                            candidate_numbers == sorted(candidate_numbers)):
                        context = text[max(0, match.start() - 150):match.end() + 50]
                        if 'ЏОКЕР' not in context and 'Џокер' not in context:
                            logger.info(f"✅ Extracted (pattern {pattern_id}): {candidate_numbers} from {draw_date}")
                            return round_number, draw_date, candidate_numbers
                except (ValueError, IndexError):
                    continue

        # STAGE 2: MEDIUM-CONFIDENCE PATTERNS
        medium_confidence_patterns = [
            (r'Добитнe\s+комбинацијe[^\n]*\n[^\n]*\n[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', 4),
            (r'^[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', 5),
        ]

        for pattern, pattern_id in medium_confidence_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                try:
                    candidate_numbers = [int(match.group(i)) for i in range(1, 8)]
                    if (all(min_num <= n <= max_num for n in candidate_numbers) and
                            len(set(candidate_numbers)) == 7 and
                            candidate_numbers == sorted(candidate_numbers)):
                        context = text[max(0, match.start() - 150):match.end() + 50]
                        if 'ЏОКЕР' not in context and 'JOKER' not in context.upper() and 'Џокер' not in context:
                            logger.info(f"✅ Extracted (pattern {pattern_id}): {candidate_numbers} from {draw_date}")
                            return round_number, draw_date, candidate_numbers
                except (ValueError, IndexError):
                    continue

        # STAGE 3: SMART FALLBACK (with validation warning)
        logger.debug("Trying smart fallback")
        sections = text.split('ЏОКЕР')
        early_text = sections[0][:1000] if len(sections) > 1 else text[:1000]

        all_numbers_found = re.findall(r'\b([1-9]|[12][0-9]|3[0-9])\b', early_text)

        if len(all_numbers_found) >= 7:
            seen = []
            for num_str in all_numbers_found:
                num = int(num_str)
                if num not in seen and min_num <= num <= max_num:
                    seen.append(num)
                if len(seen) == 7:
                    break

            if len(seen) == 7:
                numbers = sorted(seen)
                logger.warning(f"⚠️ Fallback used (VERIFY MANUALLY): {numbers} from {draw_date}")
                return round_number, draw_date, numbers

        logger.warning(f"❌ Could not extract valid numbers from PDF: {pdf_url}")
        return None

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_url}: {e}")
        return None


def scrape_recent_draws(max_pdfs=50):
    """Scrape recent draws from Serbia lottery"""
    js_data = extract_js_data()

    if not js_data:
        logger.error("No data found")
        return 0

    session = get_session()
    inserted_count = 0

    try:
        for i, report in enumerate(js_data[:max_pdfs]):
            pdf_path = report.get('OfficialReportPath')
            if not pdf_path:
                continue

            result = extract_numbers_from_pdf(pdf_path)
            if not result:
                continue

            round_number, draw_date, numbers = result

            existing = session.query(Draw).filter_by(draw_date=draw_date).first()
            if existing:
                # Update round_number if missing
                if existing.round_number is None and round_number is not None:
                    existing.round_number = round_number
                    session.commit()
                    logger.info(f"Updated round_number for {draw_date}")
                continue

            draw = Draw(
                draw_date=draw_date,
                round_number=round_number,  # ✅ NOW SAVED
                n1=numbers[0],
                n2=numbers[1],
                n3=numbers[2],
                n4=numbers[3],
                n5=numbers[4],
                n6=numbers[5],
                n7=numbers[6]
            )
            session.add(draw)
            session.commit()

            logger.info(f"✅ Inserted draw {draw_date} (kolo {round_number}): {numbers}")
            inserted_count += 1

    except Exception as e:
        session.rollback()
        logger.error(f"Error during scraping: {e}")
    finally:
        session.close()

    logger.info(f"Scraping complete: {inserted_count} new draws")
    return inserted_count


parse_pdf_for_numbers = extract_numbers_from_pdf


def scrape_all_draws():
    """Scrape full history"""
    return scrape_recent_draws(max_pdfs=1500)


if __name__ == "__main__":
    from lotto_ai.core.db import init_db
    init_db()
    logger.info("Manual scrape triggered")
    scrape_recent_draws(max_pdfs=10)