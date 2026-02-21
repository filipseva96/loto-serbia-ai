"""
Verify scraped data quality
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from lotto_ai.core.db import get_session, Draw
import pandas as pd

session = get_session()
draws = session.query(Draw).order_by(Draw.draw_date.desc()).all()
session.close()

print("=" * 70)
print("📊 DATA QUALITY REPORT")
print("=" * 70)

print(f"\n📈 Total Draws: {len(draws)}")

if draws:
    # Date range
    dates = [d.draw_date for d in draws]
    print(f"📅 Date Range: {min(dates)} to {max(dates)}")
    
    # Sample draws
    print(f"\n🎲 Latest 10 Draws:")
    print("-" * 70)
    for draw in draws[:10]:
        numbers = [draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6, draw.n7]
        print(f"  {draw.draw_date}: {numbers}")
    
    # Number frequency analysis
    all_numbers = []
    for draw in draws:
        all_numbers.extend([draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6, draw.n7])
    
    print(f"\n📊 Number Statistics:")
    print(f"   Total numbers drawn: {len(all_numbers)}")
    print(f"   Unique numbers: {len(set(all_numbers))}")
    print(f"   Min number: {min(all_numbers)}")
    print(f"   Max number: {max(all_numbers)}")
    
    # Validate range
    invalid = [n for n in all_numbers if n < 1 or n > 39]
    if invalid:
        print(f"   ⚠️  WARNING: {len(invalid)} numbers out of range (1-39)!")
    else:
        print(f"   ✅ All numbers in valid range (1-39)")
    
    # Top 10 most frequent
    from collections import Counter
    freq = Counter(all_numbers)
    print(f"\n🔥 Top 10 Most Frequent Numbers:")
    for num, count in freq.most_common(10):
        print(f"   {num:2d}: {count:3d} times ({count/len(draws)*100:.1f}%)")
    
    print(f"\n❄️  Top 10 Least Frequent Numbers:")
    for num, count in freq.most_common()[-10:]:
        print(f"   {num:2d}: {count:3d} times ({count/len(draws)*100:.1f}%)")

else:
    print("❌ No draws found in database!")

print("=" * 70)