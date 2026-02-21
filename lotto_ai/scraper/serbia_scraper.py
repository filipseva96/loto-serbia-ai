"""
Loto Serbia scraper - ENHANCED VERSION
Handles multiple PDF formats (Службени, Privremeni, etc.)
"""
import requests
import re
import io
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from PyPDF2 import PdfReader

# Fix imports when run directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from lotto_ai.config import BASE_URL, logger
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
    ENHANCED v5: Fixed Latin/Cyrillic "kolo" issue
    """
    try:
        full_url = f"https://lutrija.rs{pdf_url}"
        logger.debug(f"Downloading PDF: {full_url}")
        
        response = requests.get(full_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        # Combine all pages
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # ✅ EXTRACT ROUND NUMBER - Support both Latin and Cyrillic "kolo"
        round_match = re.search(r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)', pdf_url, re.IGNORECASE)
        if not round_match:
            # Try from PDF content
            round_match = re.search(r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)', text, re.IGNORECASE)
        
        if not round_match:
            logger.warning(f"Could not extract round number from: {pdf_url}")
            return None
        
        round_number = int(round_match.group(1))
        
        # ✅ EXTRACT DATE - Try filename first, then PDF content
        draw_date = None
        
        # Try filename date patterns
        filename_date_patterns = [
            r'(\d{2})\.(\d{2})\.(\d{4})',  # DD.MM.YYYY
            r'(\d{2})-(\d{2})-(\d{4})',    # DD-MM-YYYY
            r'од\s+(\d{2})\.(\d{2})\.(\d{4})',  # "од DD.MM.YYYY"
        ]
        
        for pattern in filename_date_patterns:
            date_match = re.search(pattern, pdf_url)
            if date_match:
                day, month, year = date_match.groups()
                draw_date = f"{year}-{month}-{day}"
                logger.debug(f"Date from filename: {draw_date}")
                break
        
        # ✅ FALLBACK: Extract date from PDF content
        if not draw_date:
            logger.debug("Date not in filename, searching PDF content...")
            
            # Pattern: "od DD.MM.YYYY" (most common in Privremeni format)
            content_date_patterns = [
                r'од\s+(\d{2})\.(\d{2})\.(\d{4})',  # од DD.MM.YYYY
                r'JOKER\s+од\s+(\d{2})\.(\d{2})\.(\d{4})',  # JOKER од DD.MM.YYYY
                r'brojeva\s+i\s+JOKER\s+од\s+(\d{2})\.(\d{2})\.(\d{4})',  # full pattern
                r'(\d{2})\.(\d{2})\.(\d{4})\.',  # First date in format DD.MM.YYYY.
            ]
            
            for pattern in content_date_patterns:
                date_match = re.search(pattern, text[:500], re.IGNORECASE)  # Search first 500 chars
                if date_match:
                    day, month, year = date_match.groups()
                    draw_date = f"{year}-{month}-{day}"
                    logger.debug(f"Date from PDF content: {draw_date}")
                    break
        
        if not draw_date:
            logger.warning(f"Could not extract date from filename or PDF content: {pdf_url}")
            return None
        
        # ✅ EXTRACT NUMBERS - Multi-stage pattern matching
        
        # STAGE 1: HIGH-CONFIDENCE PATTERNS
        high_confidence_patterns = [
            # Pattern 1: "ЛОТ О 7 О Д 39 (...)" followed by sorted numbers on next line
            (r'ЛОТ\s*О\s*7\s*О\s*Д\s*39[^\n]*\n[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', 1),
            
            # Pattern 2: "Dobitna kombinacija Loto 7/39" with sorted numbers (comma-separated)
            # Matches: "(4, 29, 38, 16, 19, 37, 7)      4, 7, 16, 19, 29, 37, 38"
            (r'Dobitna\s+kombinacija\s+Loto\s+7/39[^\d]*\([^\)]+\)\s+(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', 2),
            
            # Pattern 3: Generic - unsorted in parentheses, then sorted with commas
            (r'\([^\)]+\)\s+(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', 3),
        ]
        
        numbers = None
        matched_pattern = None
        
        for pattern, pattern_id in high_confidence_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL))
            
            for match in matches:
                try:
                    candidate_numbers = [int(match.group(i)) for i in range(1, 8)]
                    
                    # Validate: all must be between 1-39
                    if all(1 <= n <= 39 for n in candidate_numbers):
                        # Validate: all must be unique
                        if len(set(candidate_numbers)) == 7:
                            # Validate: must be sorted (we extract from sorted line)
                            if candidate_numbers == sorted(candidate_numbers):
                                # Additional check: avoid JOKER section
                                context = text[max(0, match.start()-150):match.end()+50]
                                if 'ЏОКЕР' not in context and 'Џокер' not in context:
                                    numbers = candidate_numbers
                                    matched_pattern = pattern_id
                                    logger.info(f"✅ Extracted (pattern {pattern_id}): {numbers} from {draw_date}")
                                    return round_number, draw_date, numbers
                except (ValueError, IndexError):
                    continue
        
        # STAGE 2: MEDIUM-CONFIDENCE PATTERNS
        medium_confidence_patterns = [
            # Pattern 4: First 7 space-separated numbers after "Добитнe комбинацијe"
            (r'Добитнe\s+комбинацијe[^\n]*\n[^\n]*\n[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', 4),
            
            # Pattern 5: Any line with exactly 7 space-separated sorted numbers
            (r'^[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', 5),
        ]
        
        for pattern, pattern_id in medium_confidence_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            
            for match in matches:
                try:
                    candidate_numbers = [int(match.group(i)) for i in range(1, 8)]
                    
                    if all(1 <= n <= 39 for n in candidate_numbers) and len(set(candidate_numbers)) == 7:
                        if candidate_numbers == sorted(candidate_numbers):
                            # Avoid JOKER section
                            context = text[max(0, match.start()-150):match.end()+50]
                            if 'ЏОКЕР' not in context and 'JOKER' not in context.upper() and 'Џокер' not in context:
                                numbers = candidate_numbers
                                matched_pattern = pattern_id
                                logger.info(f"✅ Extracted (pattern {pattern_id}): {numbers} from {draw_date}")
                                return round_number, draw_date, numbers
                except (ValueError, IndexError):
                    continue
        
        # STAGE 3: SMART FALLBACK
        logger.debug("Trying smart fallback")
        
        # Split by JOKER to avoid false matches
        sections = text.split('ЏОКЕР')
        if len(sections) > 1:
            early_text = sections[0][:1000]
        else:
            early_text = text[:1000]
        
        # Find all valid numbers
        all_numbers = re.findall(r'\b([1-9]|[12][0-9]|3[0-9])\b', early_text)
        
        if len(all_numbers) >= 7:
            seen = []
            for num_str in all_numbers:
                num = int(num_str)
                if num not in seen:
                    seen.append(num)
                if len(seen) == 7:
                    break
            
            if len(seen) == 7:
                numbers = sorted(seen)
                matched_pattern = "fallback"
                logger.warning(f"⚠️ Fallback used: {numbers} from {draw_date}")
                return round_number, draw_date, numbers
        
        logger.warning(f"❌ Could not extract valid numbers from PDF: {pdf_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_url}: {e}")
        return None

def scrape_recent_draws(max_pdfs=50):
    """
    Scrape recent draws from Serbia lottery
    
    Args:
        max_pdfs: Maximum number of PDFs to process
    """
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
            
            # Check if exists
            existing = session.query(Draw).filter_by(draw_date=draw_date).first()
            if existing:
                logger.info(f"Draw {draw_date} already exists")
                continue
            
            # Insert
            draw = Draw(
                draw_date=draw_date,
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
            
            logger.info(f"✅ Inserted draw {draw_date}: {numbers}")
            inserted_count += 1
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error during scraping: {e}")
    finally:
        session.close()
    
    logger.info(f"Scraping complete: {inserted_count} new draws")
    return inserted_count

# Alias for backward compatibility
parse_pdf_for_numbers = extract_numbers_from_pdf

def scrape_all_draws():
    """Scrape full history (use with caution - many PDFs)"""
    return scrape_recent_draws(max_pdfs=1500)

if __name__ == "__main__":
    from lotto_ai.core.db import init_db
    init_db()
    logger.info("Manual scrape triggered")
    scrape_recent_draws(max_pdfs=10)