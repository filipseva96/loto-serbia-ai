"""
Compare 3 different strategies
"""
import numpy as np
import pandas as pd
from lotto_ai.features.features import load_draws
from lotto_ai.models.frequency_model import frequency_probability
from lotto_ai.evaluation.backtest import (
    build_feature_matrix_for_draws,
    calculate_matches,
    prize_value,
    generate_random_portfolio
)

def generate_ticket_safe(probs, n_numbers=7):
    """Safe ticket generation"""
    numbers = probs.index.values
    probs_array = probs.values.astype(float)
    probs_array = np.clip(probs_array, 1e-10, None)
    probs_array = probs_array / probs_array.sum()
    
    ticket = np.random.choice(numbers, size=n_numbers, replace=False, p=probs_array)
    return sorted(ticket.tolist())

def strategy_1_simple_frequency(features, n_tickets=10):
    """Strategy 1: Pure frequency with gentle diversity"""
    freq_probs = frequency_probability(features)
    tickets = []
    probs_copy = freq_probs.copy()
    
    for _ in range(n_tickets):
        ticket = generate_ticket_safe(probs_copy)
        tickets.append(ticket)
        
        for num in ticket:
            probs_copy[num] *= 0.90  # gentle penalty
        probs_copy = probs_copy / probs_copy.sum()
    
    return tickets

def strategy_2_hybrid(features, n_tickets=10):
    """Strategy 2: Mix of frequency and random"""
    freq_probs = frequency_probability(features)
    tickets = []
    
    # 70% frequency-based
    for _ in range(7):
        tickets.append(generate_ticket_safe(freq_probs))
    
    # 30% pure random
    for _ in range(3):
        tickets.append(sorted(np.random.choice(range(1, 51), 7, replace=False).tolist()))
    
    return tickets

def compare_strategies(start_index=200, n_tests=100, n_tickets=10):
    """Compare all strategies"""
    print("=" * 70)
    print("🔬 3-WAY STRATEGY COMPARISON")
    print("=" * 70)
    
    df_draws = load_draws()
    results = []
    
    for i in range(start_index, start_index + n_tests):
        train_draws = df_draws.iloc[:i]
        test_draw = df_draws.iloc[i]
        actual_numbers = [test_draw[f'n{j}'] for j in range(1, 8)]
        
        features = build_feature_matrix_for_draws(train_draws)
        
        # Generate portfolios
        portfolio_1 = strategy_1_simple_frequency(features, n_tickets)
        portfolio_2 = strategy_2_hybrid(features, n_tickets)
        portfolio_3 = generate_random_portfolio(n_tickets)
        
        # Calculate matches
        matches_1 = [calculate_matches(t, actual_numbers) for t in portfolio_1]
        matches_2 = [calculate_matches(t, actual_numbers) for t in portfolio_2]
        matches_3 = [calculate_matches(t, actual_numbers) for t in portfolio_3]
        
        results.append({
            'draw_date': test_draw['draw_date'],
            's1_best': max(matches_1),
            's2_best': max(matches_2),
            's3_best': max(matches_3),
            's1_total': sum(matches_1),
            's2_total': sum(matches_2),
            's3_total': sum(matches_3),
            's1_value': sum(prize_value(m) for m in matches_1),
            's2_value': sum(prize_value(m) for m in matches_2),
            's3_value': sum(prize_value(m) for m in matches_3),
        })
        
        if (i - start_index + 1) % 20 == 0:
            print(f"✓ Tested {i - start_index + 1}/{n_tests} draws...")
    
    df = pd.DataFrame(results)
    
    print("\n" + "=" * 70)
    print("📊 RESULTS COMPARISON")
    print("=" * 70)
    
    print(f"\n🎯 Best Match per Portfolio:")
    print(f"   Strategy 1 (Frequency):  {df['s1_best'].mean():.3f}")
    print(f"   Strategy 2 (Hybrid):     {df['s2_best'].mean():.3f}")
    print(f"   Strategy 3 (Random):     {df['s3_best'].mean():.3f}")
    
    print(f"\n🎲 Total Matches:")
    print(f"   Strategy 1: {df['s1_total'].mean():.2f}")
    print(f"   Strategy 2: {df['s2_total'].mean():.2f}")
    print(f"   Strategy 3: {df['s3_total'].mean():.2f}")
    
    print(f"\n💰 Expected Value:")
    print(f"   Strategy 1: ${df['s1_value'].mean():.2f}")
    print(f"   Strategy 2: ${df['s2_value'].mean():.2f}")
    print(f"   Strategy 3: ${df['s3_value'].mean():.2f}")
    
    # Winner
    best_strategy = df[['s1_best', 's2_best', 's3_best']].mean().idxmax()
    print(f"\n🏆 Winner: {best_strategy}")
    
    df.to_csv('strategy_comparison.csv', index=False)
    print(f"\n💾 Saved to: strategy_comparison.csv")

if __name__ == "__main__":
    compare_strategies()