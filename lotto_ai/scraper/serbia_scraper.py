"""
Loto Serbia scraper - v3.2
- Primary: HTML from lutrija.rs/Results
- Retry with session and different headers
- Graceful timeout handling
- Clear error messages for cloud users
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

from lotto_ai.config import logger, MAX_NUMBER, MIN_NUMBER, NUMBERS_PER_DRAW, IS_CLOUD
from lotto_ai.core.db import get_session, Draw

# Multiple URL variants to try
RESULTS_URLS = [
    "https://www.lutrija.rs/Results?gameNo=1",
    "https://lutrija.rs/Results?gameNo=1",
]

OLD_BASE_URL = "https://lutrija.rs/Results/OfficialReports?gameNo=1"

# Rotate user agents to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


def _get_session():
    """Create a requests session with retry logic"""
    import random
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr-RS,sr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    })
    
    # Retry adapter
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


def _fetch_page(url, timeout=30):
    """Fetch a page with retry and multiple timeouts"""
    session = _get_session()
    
    timeouts_to_try = [timeout, timeout + 15, timeout + 30]
    last_error = None
    
    for t in timeouts_to_try:
        try:
            logger.debug(f"Fetching {url} (timeout={t}s)")
            response = session.get(url, timeout=t)
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectTimeout:
            last_error = f"Connection timeout ({t}s)"
            logger.warning(f"Timeout fetching {url} ({t}s), retrying...")
            continue
        except requests.exceptions.ReadTimeout:
            last_error = f"Read timeout ({t}s)"
            logger.warning(f"Read timeout {url} ({t}s), retrying...")
            continue
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            logger.warning(f"Connection error: {e}")
            continue
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP error: {e}"
            logger.warning(f"HTTP error: {e}")
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Unexpected error: {e}")
            break
    
    logger.error(f"All attempts failed for {url}: {last_error}")
    return None


# ============================================================================
# NEW SCRAPER: HTML Results Page
# ============================================================================

def scrape_results_page():
    """
    Scrape latest draw results from lutrija.rs/Results?gameNo=1
    Tries multiple URL variants.
    
    Returns:
        list of dicts with draw data, or empty list
    """
    response = None
    
    for url in RESULTS_URLS:
        logger.info(f"Trying: {url}")
        response = _fetch_page(url)
        if response:
            break
    
    if not response:
        logger.error("Could not reach lutrija.rs from this server")
        return []
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # Find draw titles: "Извештај за 16. коло - датум извлачења 24.02.2026"
        title_labels = []
        
        # Method 1: CSS selector
        title_labels = soup.select('div.Rez_Txt_Title label')
        
        # Method 2: Find by text pattern
        if not title_labels:
            for label in soup.find_all('label'):
                text = label.get_text(strip=True)
                if 'коло' in text and ('извлачења' in text or 'датум' in text):
                    title_labels.append(label)
        
        # Method 3: Find any element with the date pattern
        if not title_labels:
            for elem in soup.find_all(['label', 'span', 'div', 'p']):
                text = elem.get_text(strip=True)
                if re.search(r'\d+\.\s*коло.*\d{2}\.\d{2}\.\d{4}', text):
                    title_labels.append(elem)
        
        logger.info(f"Found {len(title_labels)} draw title(s)")
        
        if not title_labels:
            # Last resort: try to extract a single draw
            result = _extract_single_draw(soup)
            if result:
                results.append(result)
            return results
        
        for title_label in title_labels:
            text = title_label.get_text(strip=True)
            logger.debug(f"Processing: {text}")
            
            # Extract round number
            round_number = None
            round_match = re.search(r'(\d+)\.\s*коло', text)
            if round_match:
                round_number = int(round_match.group(1))
            
            # Extract date
            draw_date = None
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
            if date_match:
                day, month, year = date_match.groups()
                draw_date = f"{year}-{month}-{day}"
            
            if not draw_date:
                continue
            
            try:
                datetime.strptime(draw_date, '%Y-%m-%d')
            except ValueError:
                continue
            
            # Find numbers
            numbers = _find_numbers_near_title(title_label, soup)
            
            if numbers and len(numbers) == NUMBERS_PER_DRAW:
                if validate_numbers(numbers):
                    results.append({
                        'round_number': round_number,
                        'draw_date': draw_date,
                        'numbers': numbers
                    })
                    logger.info(f"✅ Extracted: {draw_date} "
                              f"(kolo {round_number}): {numbers}")
        
        return results
    
    except Exception as e:
        logger.error(f"Error parsing results page: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _find_numbers_near_title(title_element, soup):
    """Find the 7 lotto numbers near a draw title element"""
    
    # Strategy 1: Walk up the DOM tree
    parent = title_element.parent
    for _ in range(10):
        if parent is None:
            break
        
        number_divs = parent.select('div.Rez_Brojevi_Txt_Gray')
        if number_divs:
            numbers = []
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
        
        parent = parent.parent
    
    # Strategy 2: Next siblings
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
            
            if sibling.select('div.Rez_Txt_Title'):
                break
    
    # Strategy 3: Find all number divs between this title and the next
    numbers = []
    current = title_element.parent
    if current:
        for elem in current.find_all_next():
            # Stop at next title
            if elem.get('class') and 'Rez_Txt_Title' in ' '.join(elem.get('class', [])):
                break
            
            if elem.get('class') and 'Rez_Brojevi_Txt_Gray' in ' '.join(elem.get('class', [])):
                text = elem.get_text(strip=True)
                try:
                    num = int(text)
                    if MIN_NUMBER <= num <= MAX_NUMBER and num not in numbers:
                        numbers.append(num)
                except (ValueError, TypeError):
                    continue
            
            if len(numbers) >= NUMBERS_PER_DRAW:
                return sorted(numbers[:NUMBERS_PER_DRAW])
    
    return sorted(numbers) if len(numbers) == NUMBERS_PER_DRAW else []


def _extract_single_draw(soup):
    """Fallback: grab first set of numbers from page"""
    number_divs = soup.select('div.Rez_Brojevi_Txt_Gray')
    
    if not number_divs:
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
        return None
    
    numbers = sorted(numbers)
    
    # Find date
    draw_date = None
    round_number = None
    
    page_text = soup.get_text()
    
    # Try: "датум извлачења DD.MM.YYYY"
    date_match = re.search(r'извлачења\s+(\d{2})\.(\d{2})\.(\d{4})', page_text)
    if date_match:
        day, month, year = date_match.groups()
        draw_date = f"{year}-{month}-{day}"
    
    # Try: any DD.MM.YYYY near "коло"
    if not draw_date:
        date_match = re.search(r'коло.*?(\d{2})\.(\d{2})\.(\d{4})', page_text, re.DOTALL)
        if date_match:
            day, month, year = date_match.groups()
            draw_date = f"{year}-{month}-{day}"
    
    if not draw_date:
        draw_date = datetime.now().strftime('%Y-%m-%d')
        logger.warning(f"Using today's date as fallback: {draw_date}")
    
    round_match = re.search(r'(\d+)\.\s*коло', page_text)
    if round_match:
        round_number = int(round_match.group(1))
    
    return {
        'round_number': round_number,
        'draw_date': draw_date,
        'numbers': numbers
    }


# ============================================================================
# MANUAL INPUT (for when scraping fails on cloud)
# ============================================================================

def add_draw_manually(draw_date, numbers, round_number=None):
    """
    Manually add a draw to the database.
    
    Args:
        draw_date: 'YYYY-MM-DD' format
        numbers: list of 7 integers
        round_number: optional round/kolo number
    
    Returns:
        True if inserted, False if already exists or invalid
    """
    numbers = sorted(numbers)
    
    if not validate_numbers(numbers):
        logger.error(f"Invalid numbers: {numbers}")
        return False
    
    try:
        datetime.strptime(draw_date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"Invalid date format: {draw_date}")
        return False
    
    session = get_session()
    try:
        existing = session.query(Draw).filter_by(draw_date=draw_date).first()
        if existing:
            logger.info(f"Draw {draw_date} already exists")
            return False
        
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
        logger.info(f"✅ Manually added: {draw_date} (kolo {round_number}): {numbers}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding draw: {e}")
        return False
    finally:
        session.close()


# ============================================================================
# MAIN SCRAPE FUNCTION
# ============================================================================

def scrape_recent_draws(max_pdfs=50):
    """
    Scrape recent draws. Tries HTML first, PDF fallback.
    Returns number of new draws inserted.
    """
    inserted_count = 0
    
    # Step 1: HTML scraper
    logger.info("Trying HTML results scraper...")
    html_results = scrape_results_page()
    
    if html_results:
        session = get_session()
        try:
            for result in html_results:
                draw_date = result['draw_date']
                numbers = result['numbers']
                round_number = result.get('round_number')
                
                if not validate_numbers(numbers):
                    continue
                
                existing = session.query(Draw).filter_by(draw_date=draw_date).first()
                if existing:
                    if round_number and not existing.round_number:
                        existing.round_number = round_number
                        session.commit()
                    continue
                
                draw = Draw(
                    draw_date=draw_date,
                    round_number=round_number,
                    n1=numbers[0], n2=numbers[1], n3=numbers[2],
                    n4=numbers[3], n5=numbers[4], n6=numbers[5],
                    n7=numbers[6]
                )
                session.add(draw)
                session.commit()
                inserted_count += 1
                logger.info(f"✅ Inserted: {draw_date} (kolo {round_number}): {numbers}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving: {e}")
        finally:
            session.close()
    
    if inserted_count > 0:
        return inserted_count
    
    # Step 2: PDF fallback
    if not IS_CLOUD:
        logger.info("Trying PDF fallback (local only)...")
        return _scrape_from_pdfs(max_pdfs)
    else:
        logger.warning("Scraping failed from cloud. Use manual input or update locally.")
        return 0


def _scrape_from_pdfs(max_pdfs=50):
    """Old PDF scraper"""
    js_data = extract_js_data()
    if not js_data:
        return 0
    
    session = get_session()
    inserted_count = 0
    
    try:
        for report in js_data[:max_pdfs]:
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
                draw_date=draw_date, round_number=round_number,
                n1=numbers[0], n2=numbers[1], n3=numbers[2],
                n4=numbers[3], n5=numbers[4], n6=numbers[5],
                n7=numbers[6]
            )
            session.add(draw)
            session.commit()
            inserted_count += 1
    except Exception as e:
        session.rollback()
        logger.error(f"PDF scraping error: {e}")
    finally:
        session.close()
    
    return inserted_count


def extract_js_data():
    """Extract PDF links from old reports page"""
    response = _fetch_page(OLD_BASE_URL, timeout=15)
    if not response:
        return []
    
    try:
        match = re.search(
            r'var officialReportsTableData = (\[.*?\]);',
            response.text, re.DOTALL
        )
        if not match:
            return []
        data = json.loads(match.group(1))
        logger.info(f"Found {len(data)} official reports")
        return data
    except Exception as e:
        logger.error(f"Error parsing JS data: {e}")
        return []


def extract_numbers_from_pdf(pdf_url):
    """Legacy PDF extraction"""
    if PdfReader is None:
        return None
    
    response = _fetch_page(f"https://lutrija.rs{pdf_url}", timeout=20)
    if not response:
        return None
    
    try:
        reader = PdfReader(io.BytesIO(response.content))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        
        # Round number
        round_number = None
        for pattern in [r'(\d+)[\s.]*(?:редовно\s+)?(?:коло|kolo)']:
            m = re.search(pattern, pdf_url, re.IGNORECASE) or \
                re.search(pattern, text, re.IGNORECASE)
            if m:
                round_number = int(m.group(1))
                break
        if not round_number:
            return None
        
        # Date
        draw_date = None
        for pattern in [r'(\d{2})\.(\d{2})\.(\d{4})']:
            m = re.search(pattern, pdf_url)
            if m:
                d, mo, y = m.groups()
                draw_date = f"{y}-{mo}-{d}"
                break
        if not draw_date:
            m = re.search(r'од\s+(\d{2})\.(\d{2})\.(\d{4})', text[:500])
            if m:
                d, mo, y = m.groups()
                draw_date = f"{y}-{mo}-{d}"
        if not draw_date:
            return None
        
        # Numbers
        sections = text.split('ЏОКЕР')
        early = sections[0][:800] if len(sections) > 1 else text[:800]
        all_nums = re.findall(r'\b([1-9]|[12]\d|3[0-9])\b', early)
        
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
        logger.error(f"PDF parse error: {e}")
        return None


def validate_numbers(numbers):
    if len(numbers) != NUMBERS_PER_DRAW:
        return False
    if any(n < MIN_NUMBER or n > MAX_NUMBER for n in numbers):
        return False
    if len(set(numbers)) != NUMBERS_PER_DRAW:
        return False
    return True


parse_pdf_for_numbers = extract_numbers_from_pdf
scrape_all_draws = lambda: _scrape_from_pdfs(max_pdfs=1500)


if __name__ == "__main__":
    from lotto_ai.core.db import init_db
    init_db()
    print("Testing scraper...")
    n = scrape_recent_draws(max_pdfs=5)
    print(f"Inserted {n} new draws")