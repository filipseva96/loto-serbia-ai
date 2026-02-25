"""
Loto Serbia scraper - v3.1
Scrapes from the Results page HTML (no more PDFs)
Fallback to old PDF method for historical data
"""
import requests
import re
import io
import sys
import json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from lotto_ai.config import logger, MAX_NUMBER, MIN_NUMBER, NUMBERS_PER_DRAW
from lotto_ai.core.db import get_session, Draw

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

RESULTS_URL = "https://www.lutrija.rs/Results?gameNo=1"
OLD_BASE_URL = "https://lutrija.rs/Results/OfficialReports?gameNo=1"


# ============================================================================
# NEW SCRAPER: HTML Results Page
# ============================================================================

def scrape_results_page():
    """
    Scrape latest draw results from https://www.lutrija.rs/Results?gameNo=1
    
    Extracts numbers from div.Rez_Brojevi_Txt_Gray elements
    and draw date from div.Rez_Txt_Title > label
    
    Returns:
        list of dicts: [{'round_number': int, 'draw_date': str, 'numbers': list}, ...]
        Empty list if scraping fails
    """
    try:
        logger.info(f"Scraping results from: {RESULTS_URL}")
        response = requests.get(RESULTS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # Find all draw report sections
        # The title contains: "Извештај за 16. коло - датум извлачења 24.02.2026"
        title_labels = soup.select('div.Rez_Txt_Title label')
        
        if not title_labels:
            # Try alternative selectors
            title_labels = soup.select('.Rez_Txt_Title label')
        
        if not title_labels:
            # Try finding by text pattern
            for label in soup.find_all('label'):
                text = label.get_text(strip=True)
                if 'коло' in text and 'извлачења' in text:
                    title_labels.append(label)
        
        logger.info(f"Found {len(title_labels)} draw title(s)")
        
        if not title_labels:
            logger.warning("No draw titles found on results page")
            # Try to extract just the numbers anyway
            result = _extract_single_draw(soup)
            if result:
                results.append(result)
            return results
        
        for title_label in title_labels:
            text = title_label.get_text(strip=True)
            logger.debug(f"Processing title: {text}")
            
            # Extract round number and date from title
            # Pattern: "Извештај за 16. коло - датум извлачења 24.02.2026"
            round_number = None
            draw_date = None
            
            # Extract round number
            round_match = re.search(r'(\d+)\.\s*коло', text)
            if round_match:
                round_number = int(round_match.group(1))
            
            # Extract date (DD.MM.YYYY)
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
            if date_match:
                day, month, year = date_match.groups()
                draw_date = f"{year}-{month}-{day}"
            
            if not draw_date:
                logger.warning(f"Could not extract date from: {text}")
                continue
            
            # Validate date
            try:
                datetime.strptime(draw_date, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid date: {draw_date}")
                continue
            
            # Find the numbers container near this title
            # Navigate up to the parent section, then find number divs
            numbers = _find_numbers_near_title(title_label, soup)
            
            if numbers and len(numbers) == NUMBERS_PER_DRAW:
                results.append({
                    'round_number': round_number,
                    'draw_date': draw_date,
                    'numbers': numbers
                })
                logger.info(f"✅ Extracted: {draw_date} (kolo {round_number}): {numbers}")
            else:
                logger.warning(f"Could not extract valid numbers for {draw_date}, "
                             f"got: {numbers}")
        
        return results
    
    except requests.RequestException as e:
        logger.error(f"Network error scraping results: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping results page: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _find_numbers_near_title(title_element, soup):
    """
    Find the 7 lotto numbers associated with a draw title.
    
    Strategy: 
    1. Look in the parent/ancestor container for Rez_Brojevi_Txt_Gray divs
    2. If that fails, look at siblings
    3. If that fails, search the whole page
    """
    numbers = []
    
    # Strategy 1: Walk up to find the containing section
    parent = title_element.parent
    for _ in range(10):  # Walk up max 10 levels
        if parent is None:
            break
        
        number_divs = parent.select('div.Rez_Brojevi_Txt_Gray')
        if number_divs:
            # Extract numbers
            for div in number_divs:
                text = div.get_text(strip=True)
                try:
                    num = int(text)
                    if MIN_NUMBER <= num <= MAX_NUMBER:
                        numbers.append(num)
                except (ValueError, TypeError):
                    continue
            
            if len(numbers) >= NUMBERS_PER_DRAW:
                # Take only the first 7 (in case there are JOKER numbers too)
                return sorted(numbers[:NUMBERS_PER_DRAW])
        
        parent = parent.parent
    
    # Strategy 2: Look at next siblings of the title's parent
    numbers = []
    parent = title_element.parent
    if parent:
        for sibling in parent.find_next_siblings():
            number_divs = sibling.select('div.Rez_Brojevi_Txt_Gray')
            if number_divs:
                for div in number_divs:
                    text = div.get_text(strip=True)
                    try:
                        num = int(text)
                        if MIN_NUMBER <= num <= MAX_NUMBER:
                            numbers.append(num)
                    except (ValueError, TypeError):
                        continue
                
                if len(numbers) >= NUMBERS_PER_DRAW:
                    return sorted(numbers[:NUMBERS_PER_DRAW])
            
            # Stop if we hit another title (next draw section)
            if sibling.select('div.Rez_Txt_Title'):
                break
    
    return sorted(numbers[:NUMBERS_PER_DRAW]) if len(numbers) >= NUMBERS_PER_DRAW else numbers


def _extract_single_draw(soup):
    """
    Fallback: extract numbers from the first set of Rez_Brojevi_Txt_Gray divs
    on the page, regardless of section structure.
    """
    number_divs = soup.select('div.Rez_Brojevi_Txt_Gray')
    
    if not number_divs:
        logger.warning("No Rez_Brojevi_Txt_Gray divs found anywhere on page")
        return None
    
    numbers = []
    for div in number_divs:
        text = div.get_text(strip=True)
        try:
            num = int(text)
            if MIN_NUMBER <= num <= MAX_NUMBER:
                numbers.append(num)
        except (ValueError, TypeError):
            continue
        
        if len(numbers) == NUMBERS_PER_DRAW:
            break
    
    if len(numbers) != NUMBERS_PER_DRAW:
        logger.warning(f"Expected {NUMBERS_PER_DRAW} numbers, found {len(numbers)}: {numbers}")
        return None
    
    numbers = sorted(numbers)
    
    # Try to find date
    draw_date = None
    round_number = None
    
    for label in soup.find_all('label'):
        text = label.get_text(strip=True)
        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if date_match and 'коло' in text:
            day, month, year = date_match.groups()
            draw_date = f"{year}-{month}-{day}"
            
            round_match = re.search(r'(\d+)\.\s*коло', text)
            if round_match:
                round_number = int(round_match.group(1))
            break
    
    # Also try from any text on page
    if not draw_date:
        page_text = soup.get_text()
        date_match = re.search(r'извлачења\s+(\d{2})\.(\d{2})\.(\d{4})', page_text)
        if date_match:
            day, month, year = date_match.groups()
            draw_date = f"{year}-{month}-{day}"
    
    if not draw_date:
        draw_date = datetime.now().strftime('%Y-%m-%d')
        logger.warning(f"Could not find date, using today: {draw_date}")
    
    logger.info(f"✅ Fallback extracted: {draw_date} (kolo {round_number}): {numbers}")
    
    return {
        'round_number': round_number,
        'draw_date': draw_date,
        'numbers': numbers
    }


def scrape_recent_draws(max_pdfs=50):
    """
    Scrape recent draws - tries new HTML method first, falls back to PDF.
    
    Args:
        max_pdfs: Maximum PDFs to process (only used for PDF fallback)
    
    Returns:
        Number of new draws inserted
    """
    inserted_count = 0
    
    # ---- STEP 1: Try new HTML scraper ----
    logger.info("Trying HTML results page scraper...")
    html_results = scrape_results_page()
    
    if html_results:
        session = get_session()
        try:
            for result in html_results:
                draw_date = result['draw_date']
                numbers = result['numbers']
                round_number = result.get('round_number')
                
                if not validate_numbers(numbers):
                    logger.warning(f"Invalid numbers for {draw_date}: {numbers}")
                    continue
                
                # Check if exists
                existing = session.query(Draw).filter_by(draw_date=draw_date).first()
                if existing:
                    # Update round_number if we have it and existing doesn't
                    if round_number and not existing.round_number:
                        existing.round_number = round_number
                        session.commit()
                        logger.info(f"Updated round_number for {draw_date}")
                    else:
                        logger.info(f"Draw {draw_date} already exists")
                    continue
                
                # Insert new draw
                draw = Draw(
                    draw_date=draw_date,
                    round_number=round_number,
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
                
                logger.info(f"✅ Inserted draw {draw_date} "
                          f"(kolo {round_number}): {numbers}")
                inserted_count += 1
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving HTML results: {e}")
        finally:
            session.close()
    
    if inserted_count > 0:
        logger.info(f"HTML scraper: {inserted_count} new draws inserted")
        return inserted_count
    
    # ---- STEP 2: Fallback to PDF scraper ----
    logger.info("HTML scraper found no new draws, trying PDF fallback...")
    pdf_count = _scrape_from_pdfs(max_pdfs)
    
    total = inserted_count + pdf_count
    logger.info(f"Scraping complete: {total} new draws total")
    return total


def _scrape_from_pdfs(max_pdfs=50):
    """Old PDF-based scraper as fallback"""
    js_data = extract_js_data()
    
    if not js_data:
        logger.warning("No PDF data found (fallback)")
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
                if round_number and not existing.round_number:
                    existing.round_number = round_number
                    session.commit()
                continue
            
            draw = Draw(
                draw_date=draw_date,
                round_number=round_number,
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
            
            logger.info(f"✅ PDF: Inserted {draw_date} (kolo {round_number}): {numbers}")
            inserted_count += 1
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error during PDF scraping: {e}")
    finally:
        session.close()
    
    return inserted_count


# ============================================================================
# OLD PDF SCRAPER (kept for historical data)
# ============================================================================

def extract_js_data():
    """Extract officialReportsTableData from JavaScript"""
    try:
        response = requests.get(OLD_BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        match = re.search(
            r'var officialReportsTableData = (\[.*?\]);',
            response.text,
            re.DOTALL
        )
        
        if not match:
            logger.warning("Could not find officialReportsTableData in page")
            return []
        
        data = json.loads(match.group(1))
        logger.info(f"Found {len(data)} official reports")
        return data
    
    except Exception as e:
        logger.error(f"Error extracting JS data: {e}")
        return []


def extract_numbers_from_pdf(pdf_url):
    """Download PDF and extract winning numbers (legacy method)"""
    if PdfReader is None:
        logger.error("PyPDF2 not installed")
        return None
    
    try:
        full_url = f"https://lutrija.rs{pdf_url}"
        response = requests.get(full_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Extract round number
        round_number = None
        for pattern in [r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)']:
            match = re.search(pattern, pdf_url, re.IGNORECASE)
            if match:
                round_number = int(match.group(1))
                break
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                round_number = int(match.group(1))
                break
        
        if round_number is None:
            return None
        
        # Extract date
        draw_date = None
        for pattern in [r'(\d{2})\.(\d{2})\.(\d{4})']:
            match = re.search(pattern, pdf_url)
            if match:
                day, month, year = match.groups()
                draw_date = f"{year}-{month}-{day}"
                break
        
        if not draw_date:
            for pattern in [r'од\s+(\d{2})\.(\d{2})\.(\d{4})',
                          r'(\d{2})\.(\d{2})\.(\d{4})\.']:
                match = re.search(pattern, text[:500], re.IGNORECASE)
                if match:
                    day, month, year = match.groups()
                    draw_date = f"{year}-{month}-{day}"
                    break
        
        if not draw_date:
            return None
        
        try:
            datetime.strptime(draw_date, '%Y-%m-%d')
        except ValueError:
            return None
        
        # Extract numbers
        patterns = [
            r'ЛОТ\s*О\s*7\s*О\s*Д\s*39[^\n]*\n[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)',
            r'\([^\)]+\)\s+(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)',
            r'^[^\d]*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL))
            for match in matches:
                try:
                    nums = [int(match.group(i)) for i in range(1, 8)]
                    if validate_numbers(nums) and nums == sorted(nums):
                        context = text[max(0, match.start() - 150):match.end() + 50]
                        if 'ЏОКЕР' not in context and 'Џокер' not in context:
                            return round_number, draw_date, nums
                except (ValueError, IndexError):
                    continue
        
        # Fallback
        sections = text.split('ЏОКЕР')
        early_text = sections[0][:800] if len(sections) > 1 else text[:800]
        all_nums = re.findall(r'\b([1-9]|[12]\d|3[0-9])\b', early_text)
        
        if len(all_nums) >= 7:
            seen = []
            for s in all_nums:
                n = int(s)
                if MIN_NUMBER <= n <= MAX_NUMBER and n not in seen:
                    seen.append(n)
                if len(seen) == 7:
                    break
            
            if len(seen) == 7 and validate_numbers(seen):
                return round_number, draw_date, sorted(seen)
        
        return None
    
    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_url}: {e}")
        return None


def validate_numbers(numbers):
    """Validate extracted numbers"""
    if len(numbers) != NUMBERS_PER_DRAW:
        return False
    if any(n < MIN_NUMBER or n > MAX_NUMBER for n in numbers):
        return False
    if len(set(numbers)) != NUMBERS_PER_DRAW:
        return False
    return True


def scrape_all_draws():
    """Scrape full history via PDFs"""
    return _scrape_from_pdfs(max_pdfs=1500)


# Keep old name for backward compatibility
parse_pdf_for_numbers = extract_numbers_from_pdf


if __name__ == "__main__":
    from lotto_ai.core.db import init_db
    init_db()
    
    print("=" * 60)
    print("Testing HTML scraper...")
    print("=" * 60)
    
    results = scrape_results_page()
    
    if results:
        for r in results:
            print(f"  {r['draw_date']} (kolo {r['round_number']}): {r['numbers']}")
    else:
        print("  No results from HTML scraper")
    
    print(f"\nInserting to database...")
    n = scrape_recent_draws(max_pdfs=5)
    print(f"Inserted {n} new draws")