import numpy as np
import pandas as pd
from datetime import datetime
from lotto_ai.features.features import load_draws
from lotto_ai.models.ensemble_advanced import advanced_ensemble
from lotto_ai.models.portfolio import generate_diversified_portfolio, portfolio_stats
from lotto_ai.models.generator import generate_ticket

# -----------------------------
# Metrics
# -----------------------------
def calculate_matches(predicted, actual):
    """Count how many numbers match"""
    return len(set(predicted) & set(actual))

def prize_value(matches):
    """Approximate prize values (CAD)"""
    prize_table = {
        7: 10_000_000,  # Jackpot (varies)
        6: 100_000,
        5: 1_500,
        4: 50,
        3: 20,
        2: 0,
        1: 0,
        0: 0
    }
    return prize_table.get(matches, 0)

# -----------------------------
# Random baseline
# -----------------------------
def generate_random_ticket():
    """Pure random ticket"""
    return sorted(np.random.choice(range(1, 51), size=7, replace=False).tolist())

def generate_random_portfolio(n_tickets=10):
    """Random portfolio"""
    return [generate_random_ticket() for _ in range(n_tickets)]

# -----------------------------
# Build features for subset
# -----------------------------
def build_feature_matrix_for_draws(df_draws, window=10):
    """Build features using only historical draws"""
    NUMBERS = range(1, 51)
    records = []
    
    for number in NUMBERS:
        appeared = df_draws[
            (df_draws[[f"n{i}" for i in range(1, 8)]] == number).any(axis=1)
        ]
        hits = appeared.index.tolist()
        
        for i in range(1, len(df_draws)):
            past_hits = [h for h in hits if h < i]
            records.append({
                "number": number,
                "draw_index": i,
                "freq": len(past_hits) / i if i > 0 else 0,
                "gap": i - past_hits[-1] if past_hits else i,
                "rolling_freq": sum(h >= i - window for h in past_hits) / window,
                "hit": int(i in hits)
            })
    
    return pd.DataFrame(records)

# -----------------------------
# Backtest with portfolios
# -----------------------------
def backtest_portfolio(start_index=100, n_tests=100, n_tickets=10):
    """
    Backtest multi-ticket strategy vs random
    """
    print("=" * 70)
    print("🎓 ADVANCED BACKTEST: Portfolio Strategy vs Random")
    print("=" * 70)
    print(f"📊 Configuration:")
    print(f"   • Portfolio size: {n_tickets} tickets")
    print(f"   • Test draws: {n_tests}")
    print(f"   • Training window: {start_index} draws")
    print("=" * 70)
    
    df_draws = load_draws()
    
    if len(df_draws) < start_index + n_tests:
        print(f"⚠️ Not enough data. Need {start_index + n_tests}, have {len(df_draws)}")
        return None
    
    results = []
    
    for i in range(start_index, start_index + n_tests):
        train_draws = df_draws.iloc[:i]
        test_draw = df_draws.iloc[i]
        
        actual_numbers = [test_draw[f'n{j}'] for j in range(1, 8)]
        
        # Build features
        features = build_feature_matrix_for_draws(train_draws)
        
        # Generate AI portfolio
        ai_probs = advanced_ensemble(features)
        ai_portfolio = generate_diversified_portfolio(ai_probs, n_tickets=n_tickets)
        
        # Generate random portfolio
        random_portfolio = generate_random_portfolio(n_tickets=n_tickets)
        
        # Calculate best match in each portfolio
        ai_matches = [calculate_matches(ticket, actual_numbers) for ticket in ai_portfolio]
        random_matches = [calculate_matches(ticket, actual_numbers) for ticket in random_portfolio]
        
        ai_best = max(ai_matches)
        random_best = max(random_matches)
        
        # Calculate total value
        ai_value = sum(prize_value(m) for m in ai_matches)
        random_value = sum(prize_value(m) for m in random_matches)
        
        # Portfolio stats
        ai_stats = portfolio_stats(ai_portfolio)
        
        results.append({
            'draw_date': test_draw['draw_date'],
            'draw_index': i,
            'actual': actual_numbers,
            'ai_best_match': ai_best,
            'random_best_match': random_best,
            'ai_total_matches': sum(ai_matches),
            'random_total_matches': sum(random_matches),
            'ai_value': ai_value,
            'random_value': random_value,
            'ai_coverage': ai_stats['coverage'],
            'ai_overlap': ai_stats['avg_overlap'],
            'ai_better': ai_best > random_best
        })
        
        if (i - start_index + 1) % 20 == 0:
            print(f"✓ Tested {i - start_index + 1}/{n_tests} draws...")
    
    return pd.DataFrame(results)

# -----------------------------
# Advanced analysis
# -----------------------------
def analyze_portfolio_results(results_df):
    """Comprehensive analysis with expected value"""
    print("\n" + "=" * 70)
    print("📊 PORTFOLIO BACKTEST RESULTS")
    print("=" * 70)
    
    total_tests = len(results_df)
    
    # Best match per portfolio
    print(f"\n🎯 Best Match per Portfolio:")
    print(f"   AI:     {results_df['ai_best_match'].mean():.3f} avg")
    print(f"   Random: {results_df['random_best_match'].mean():.3f} avg")
    print(f"   Δ:      {results_df['ai_best_match'].mean() - results_df['random_best_match'].mean():+.3f}")
    
    # Total matches across all tickets
    print(f"\n🎲 Total Matches (sum of all tickets):")
    print(f"   AI:     {results_df['ai_total_matches'].mean():.2f} avg")
    print(f"   Random: {results_df['random_total_matches'].mean():.2f} avg")
    print(f"   Δ:      {results_df['ai_total_matches'].mean() - results_df['random_total_matches'].mean():+.2f}")
    
    # Expected value
    print(f"\n💰 Expected Value (prize money):")
    print(f"   AI:     ${results_df['ai_value'].mean():,.2f} avg")
    print(f"   Random: ${results_df['random_value'].mean():,.2f} avg")
    print(f"   Δ:      ${results_df['ai_value'].mean() - results_df['random_value'].mean():+,.2f}")
    
    # Win rate
    ai_wins = results_df['ai_better'].sum()
    print(f"\n🏆 Head-to-Head (best match):")
    print(f"   AI Wins:     {ai_wins} ({ai_wins/total_tests*100:.1f}%)")
    print(f"   Random Wins: {total_tests - ai_wins} ({(total_tests-ai_wins)/total_tests*100:.1f}%)")
    
    # Portfolio quality
    print(f"\n📦 Portfolio Quality:")
    print(f"   Avg Coverage:    {results_df['ai_coverage'].mean():.1f} / 50 numbers")
    print(f"   Avg Overlap:     {results_df['ai_overlap'].mean():.2f} numbers/ticket")
    
    # Distribution of best matches
    print(f"\n🎯 Best Match Distribution (AI):")
    for matches in range(8):
        count = (results_df['ai_best_match'] == matches).sum()
        pct = count / total_tests * 100
        bar = "█" * int(pct / 2)
        print(f"   {matches} matches: {count:3d} ({pct:5.1f}%) {bar}")
    
    # Statistical test
    from scipy import stats
    t_stat, p_value = stats.ttest_rel(
        results_df['ai_best_match'],
        results_df['random_best_match']
    )
    
    print(f"\n📉 Statistical Significance:")
    print(f"   t-statistic: {t_stat:.4f}")
    print(f"   p-value:     {p_value:.4f}")
    
    if p_value < 0.05:
        if results_df['ai_best_match'].mean() > results_df['random_best_match'].mean():
            print(f"   ✅ AI SIGNIFICANTLY BETTER (p < 0.05)")
        else:
            print(f"   ⚠️ AI significantly worse")
    else:
        print(f"   ⚪ No significant difference")
    
    # ROI analysis (assuming $5/ticket)
    cost_per_draw = 10 * 5  # 10 tickets × $5
    ai_roi = (results_df['ai_value'].sum() - cost_per_draw * total_tests) / (cost_per_draw * total_tests) * 100
    random_roi = (results_df['random_value'].sum() - cost_per_draw * total_tests) / (cost_per_draw * total_tests) * 100
    
    print(f"\n💵 ROI Analysis (${cost_per_draw} per draw):")
    print(f"   AI:     {ai_roi:+.2f}%")
    print(f"   Random: {random_roi:+.2f}%")
    print(f"   Δ:      {ai_roi - random_roi:+.2f}%")
    
    print("\n" + "=" * 70)
    
    return {
        'ai_avg_best': results_df['ai_best_match'].mean(),
        'random_avg_best': results_df['random_best_match'].mean(),
        'p_value': p_value,
        'ai_roi': ai_roi,
        'random_roi': random_roi
    }

# -----------------------------
# Main
# -----------------------------
def main():
    """Run portfolio backtest"""
    results = backtest_portfolio(start_index=200, n_tests=100, n_tickets=10)
    
    if results is not None:
        stats = analyze_portfolio_results(results)
        
        results.to_csv('backtest_portfolio_results.csv', index=False)
        print(f"\n💾 Results saved to: backtest_portfolio_results.csv")

if __name__ == "__main__":
    main()