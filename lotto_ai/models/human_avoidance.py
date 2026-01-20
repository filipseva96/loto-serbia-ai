"""
Game-theoretic human avoidance strategy
Based on research: most players pick birthdays, patterns, lucky numbers
"""
import numpy as np

# Empirical data on most-picked numbers (you can customize this)
POPULAR_NUMBERS = {
    7: 2.5,   # "lucky 7"
    13: 1.8,  # superstition
    **{i: 2.0 for i in range(1, 32)}  # birthdays (1-31)
}

def apply_human_avoidance(probs, strength=0.7):
    """
    Penalize numbers that humans over-pick
    
    Args:
        strength: How much to penalize (0.5 = 50% reduction)
    
    Returns:
        Adjusted probabilities that favor unpopular numbers
    """
    adjusted = probs.copy()
    
    for num, penalty in POPULAR_NUMBERS.items():
        if num in adjusted.index:
            adjusted[num] *= (1 - strength * (penalty - 1) / 10)
    
    # Normalize
    return adjusted / adjusted.sum()

def expected_payout_adjustment(probs, jackpot_size=10_000_000, avg_players=1_000_000):
    """
    Adjust for expected payout given number popularity
    
    E[payout] = jackpot / (1 + popularity_factor * avg_players)
    
    Popular numbers → more winners → smaller share
    """
    adjusted = probs.copy()
    
    for num in adjusted.index:
        popularity = POPULAR_NUMBERS.get(num, 1.0)
        
        # Boost unpopular numbers
        if popularity < 1.5:
            adjusted[num] *= 1.2
        elif popularity > 2.0:
            adjusted[num] *= 0.8
    
    return adjusted / adjusted.sum()

def balance_constraints(ticket):
    """
    Check if ticket satisfies balance constraints
    """
    odd_count = sum(n % 2 for n in ticket)
    low_count = sum(n <= 25 for n in ticket)
    consecutive = any(ticket[i] + 1 == ticket[i+1] for i in range(len(ticket)-1))
    
    return (
        2 <= odd_count <= 5 and
        2 <= low_count <= 5 and
        not consecutive  # avoid obvious patterns
    )