"""
Quick script to update draws and push to GitHub.
Run this locally after each draw (Tuesday/Friday after 20:00).

Usage:
    python update_draws.py
    python update_draws.py --manual 2026-02-25 1,13,16,20,25,26,28
    python update_draws.py --manual 2026-02-25 1,13,16,20,25,26,28 --kolo 17
"""
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from lotto_ai.core.db import init_db, get_session, Draw
from lotto_ai.scraper.serbia_scraper import scrape_recent_draws, add_draw_manually
from lotto_ai.config import logger


def show_latest():
    """Show latest draws in database"""
    session = get_session()
    try:
        draws = session.query(Draw).order_by(Draw.draw_date.desc()).limit(5).all()
        total = session.query(Draw).count()
        
        print(f"\n📊 Total draws: {total}")
        print(f"📅 Latest 5:")
        for d in draws:
            nums = d.get_numbers()
            kolo = f" (kolo {d.round_number})" if d.round_number else ""
            print(f"   {d.draw_date}{kolo}: {nums}")
    finally:
        session.close()


def auto_scrape():
    """Try automatic scraping"""
    print("\n🔄 Trying auto-scrape from lutrija.rs...")
    n = scrape_recent_draws(max_pdfs=10)
    
    if n > 0:
        print(f"✅ Added {n} new draws!")
        return True
    else:
        print("⚠️  No new draws found via scraping")
        return False


def manual_input():
    """Interactive manual input"""
    print("\n✏️  Manual input mode")
    print("   (Type 'done' to finish)\n")
    
    added = 0
    
    while True:
        date_str = input("   Date (YYYY-MM-DD) or 'done': ").strip()
        
        if date_str.lower() == 'done':
            break
        
        # Validate date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print("   ❌ Invalid date format. Use YYYY-MM-DD")
            continue
        
        nums_str = input("   Numbers (comma-separated): ").strip()
        try:
            nums = [int(x.strip()) for x in nums_str.split(",")]
        except ValueError:
            print("   ❌ Invalid numbers")
            continue
        
        if len(nums) != 7:
            print(f"   ❌ Need 7 numbers, got {len(nums)}")
            continue
        
        kolo_str = input("   Kolo (optional, press Enter to skip): ").strip()
        kolo = int(kolo_str) if kolo_str else None
        
        if add_draw_manually(date_str, nums, kolo):
            print(f"   ✅ Added: {date_str} {sorted(nums)}")
            added += 1
        else:
            print(f"   ⚠️  Already exists or invalid")
    
    return added


def git_push():
    """Commit and push database to GitHub"""
    print("\n📤 Pushing to GitHub...")
    
    db_path = Path("data/loto_serbia.db")
    if not db_path.exists():
        print("   ❌ Database not found")
        return False
    
    try:
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain", str(db_path)],
            capture_output=True, text=True
        )
        
        if not result.stdout.strip():
            print("   ℹ️  No database changes to push")
            return True
        
        # Add, commit, push
        subprocess.run(["git", "add", str(db_path)], check=True)
        
        today = datetime.now().strftime('%Y-%m-%d %H:%M')
        subprocess.run(
            ["git", "commit", "-m", f"Update draws database {today}"],
            check=True
        )
        
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print("   ✅ Pushed to GitHub!")
        print("   ☁️  Streamlit Cloud will auto-update in ~1 minute")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Git error: {e}")
        return False
    except FileNotFoundError:
        print("   ❌ Git not found. Push manually:")
        print('      git add data/loto_serbia.db')
        print('      git commit -m "Update draws"')
        print('      git push origin main')
        return False


def main():
    init_db()
    
    print("=" * 60)
    print("🇷🇸 LOTO SERBIA - UPDATE DRAWS")
    print("=" * 60)
    
    # Check command line args
    if len(sys.argv) >= 4 and sys.argv[1] == '--manual':
        # Quick manual mode: python update_draws.py --manual 2026-02-25 1,13,16,20,25,26,28
        date_str = sys.argv[2]
        nums = [int(x.strip()) for x in sys.argv[3].split(",")]
        kolo = None
        
        if len(sys.argv) >= 6 and sys.argv[4] == '--kolo':
            kolo = int(sys.argv[5])
        
        if add_draw_manually(date_str, nums, kolo):
            print(f"✅ Added: {date_str} {sorted(nums)}")
        else:
            print(f"⚠️  Already exists or invalid")
        
        show_latest()
        git_push()
        return
    
    # Interactive mode
    show_latest()
    
    # Try auto-scrape first
    scraped = auto_scrape()
    
    if not scraped:
        print("\n" + "-" * 40)
        response = input("\nDo you want to enter draws manually? (y/n): ").strip().lower()
        
        if response == 'y':
            manual_input()
    
    show_latest()
    
    # Push to GitHub
    print("\n" + "-" * 40)
    response = input("\nPush to GitHub? (y/n): ").strip().lower()
    
    if response == 'y':
        git_push()
    else:
        print("\n💡 To push later:")
        print("   git add data/loto_serbia.db")
        print('   git commit -m "Update draws"')
        print("   git push origin main")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()