"""
Analyze Privremeni izvještaj format
"""
import requests
from PyPDF2 import PdfReader
import io
import re

TEST_URL = "https://lutrija.rs/DLSFiles/Dokumenti/TREZOR%20-%20Izvestaji/Privremeni%20izve%C5%A1taj%20Lota%2090%20kolo%202023.pdf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

print("=" * 70)
print("🔍 ANALYZING PRIVREMENI FORMAT")
print("=" * 70)
print(f"URL: {TEST_URL}\n")

try:
    response = requests.get(TEST_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    
    pdf = PdfReader(io.BytesIO(response.content))
    print(f"✅ Downloaded: {len(pdf.pages)} pages\n")
    
    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        
        print(f"📄 PAGE {page_num}:")
        print("-" * 70)
        # Show full text (these PDFs are usually short)
        print(text)
        print("-" * 70)
        
        print("\n🔍 DATE PATTERNS:")
        
        # Try to find dates in various formats
        date_patterns = [
            (r'(\d{2})\.(\d{2})\.(\d{4})', 'DD.MM.YYYY'),
            (r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})', 'D.M.YYYY with spaces'),
            (r'od\s+(\d{2})\.(\d{2})\.(\d{4})', 'od DD.MM.YYYY'),
            (r'(\d{4})\.(\d{2})\.(\d{2})', 'YYYY.MM.DD'),
            (r'(\d{2})-(\d{2})-(\d{4})', 'DD-MM-YYYY'),
        ]
        
        for pattern, name in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                print(f"  ✅ {name}: {matches}")
        
        print("\n🔢 NUMBER EXTRACTION:")
        
        # Look for winning numbers
        number_patterns = [
            (r'Dobitna\s+kombinacija.*?(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', 'Dobitna kombinacija'),
            (r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', 'Parentheses with commas'),
            (r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', '7 space-separated'),
        ]
        
        for pattern, name in number_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                try:
                    nums = [int(match.group(i)) for i in range(1, 8)]
                    if all(1 <= n <= 39 for n in nums):
                        print(f"  ✅ {name}: {nums}")
                        print(f"     Context: ...{text[max(0, match.start()-50):match.end()+50]}...")
                except:
                    pass
        
        print("\n" + "=" * 70 + "\n")

except Exception as e:
    print(f"❌ ERROR: {e}")