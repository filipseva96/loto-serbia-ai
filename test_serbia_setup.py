"""
Test script for Serbia setup
"""
from lotto_ai.core.db import init_db, get_session, Draw
from lotto_ai.scraper.serbia_scraper import scrape_recent_draws
from lotto_ai.features.features import build_feature_matrix, load_draws
from lotto_ai.models.production_model import generate_adaptive_portfolio
from lotto_ai.config import logger, NUMBER_RANGE

def test_database():
    """Test database initialization"""
    print("=" * 70)
    print("TEST 1: Database Initialization")
    print("=" * 70)
    
    try:
        init_db()
        session = get_session()
        count = session.query(Draw).count()
        session.close()
        
        print(f"✅ Database initialized successfully")
        print(f"   Current draws: {count}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_scraping():
    """Test PDF scraping"""
    print("\n" + "=" * 70)
    print("TEST 2: PDF Scraping")
    print("=" * 70)
    
    try:
        inserted = scrape_recent_draws(max_pdfs=5)
        print(f"✅ Scraping successful")
        print(f"   Inserted draws: {inserted}")
        return True
    except Exception as e:
        print(f"❌ Scraping test failed: {e}")
        return False

def test_features():
    """Test feature engineering"""
    print("\n" + "=" * 70)
    print("TEST 3: Feature Engineering")
    print("=" * 70)
    
    try:
        df = load_draws()
        print(f"   Loaded {len(df)} draws")
        
        features = build_feature_matrix()
        print(f"   Generated {len(features)} feature rows")
        
        unique_numbers = features['number'].nunique()
        expected = NUMBER_RANGE[1] - NUMBER_RANGE[0] + 1
        
        if unique_numbers == expected:
            print(f"✅ Feature matrix correct (1-{NUMBER_RANGE[1]})")
            return True
        else:
            print(f"❌ Wrong number range: {unique_numbers} (expected {expected})")
            return False
    except Exception as e:
        print(f"❌ Feature test failed: {e}")
        return False

def test_generation():
    """Test ticket generation"""
    print("\n" + "=" * 70)
    print("TEST 4: Ticket Generation")
    print("=" * 70)
    
    try:
        features = build_feature_matrix()
        portfolio, weights = generate_adaptive_portfolio(features, n_tickets=5)
        
        print(f"✅ Generated {len(portfolio)} tickets")
        
        # Validate ranges
        all_valid = True
        for i, ticket in enumerate(portfolio, 1):
            if any(n < NUMBER_RANGE[0] or n > NUMBER_RANGE[1] for n in ticket):
                print(f"❌ Ticket {i} has invalid numbers: {ticket}")
                all_valid = False
            else:
                print(f"   Ticket {i}: {ticket}")
        
        return all_valid
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        return False

def main():
    print("\n" + "🎰" * 35)
    print("LOTO SERBIA SETUP TEST")
    print("🎰" * 35 + "\n")
    
    tests = [
        test_database,
        test_scraping,
        test_features,
        test_generation
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - System ready for Serbia!")
    else:
        print("❌ Some tests failed - please fix before deployment")
    
    print("=" * 70)

if __name__ == "__main__":
    main()