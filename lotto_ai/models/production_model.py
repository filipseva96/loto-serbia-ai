"""
Production model with adaptive learning
"""
import numpy as np
from lotto_ai.models.frequency_model import frequency_probability
from lotto_ai.learning.adaptive_learner import AdaptiveLearner

def generate_ticket_safe(probs, n_numbers=7, max_attempts=100):
    """Generate a single ticket from probability distribution"""
    numbers = probs.index.values
    probs_array = probs.values.astype(float)
    
    probs_array = np.clip(probs_array, 1e-10, None)
    probs_array = probs_array / probs_array.sum()
    
    for attempt in range(max_attempts):
        ticket = np.random.choice(numbers, size=n_numbers, replace=False, p=probs_array)
        ticket = sorted(ticket.tolist())
        
        odd_count = sum(n % 2 for n in ticket)
        if 2 <= odd_count <= 5:
            return ticket
    
    return ticket

def generate_adaptive_portfolio(features, n_tickets=10, use_adaptive=True):
    """
    Generate portfolio with adaptive weights
    
    Args:
        features: Feature matrix
        n_tickets: Number of tickets
        use_adaptive: If True, use learned weights; else use default
    
    Returns:
        Tuple of (portfolio, weights_used)
    """
    portfolio = []
    
    # Get adaptive weights if enabled
    if use_adaptive:
        learner = AdaptiveLearner()
        weights = learner.get_current_weights('hybrid_v1')
        freq_ratio = weights.get('frequency_ratio', {}).get('value', 0.70)
        random_ratio = weights.get('random_ratio', {}).get('value', 0.30)
        print(f"🧠 Using adaptive weights: {freq_ratio:.0%} freq / {random_ratio:.0%} random")
    else:
        freq_ratio = 0.70
        random_ratio = 0.30
        print(f"📊 Using default weights: {freq_ratio:.0%} freq / {random_ratio:.0%} random")
    
    # Calculate number of each ticket type
    n_freq = int(n_tickets * freq_ratio)
    n_random = n_tickets - n_freq
    
    # Generate frequency-based tickets
    freq_probs = frequency_probability(features, smoothing=1.0)
    for i in range(n_freq):
        ticket = generate_ticket_safe(freq_probs)
        portfolio.append(ticket)
    
    # Generate random tickets
    for i in range(n_random):
        ticket = sorted(np.random.choice(range(1, 51), 7, replace=False).tolist())
        odd_count = sum(n % 2 for n in ticket)
        if 2 <= odd_count <= 5:
            portfolio.append(ticket)
        else:
            ticket = sorted(np.random.choice(range(1, 51), 7, replace=False).tolist())
            portfolio.append(ticket)
    
    weights_used = {
        'frequency_ratio': freq_ratio,
        'random_ratio': random_ratio,
        'n_freq_tickets': n_freq,
        'n_random_tickets': n_random
    }
    
    return portfolio, weights_used

def portfolio_statistics(portfolio):
    """Calculate portfolio quality metrics"""
    all_numbers = set()
    for ticket in portfolio:
        all_numbers.update(ticket)
    
    overlaps = []
    for i in range(len(portfolio)):
        for j in range(i+1, len(portfolio)):
            overlap = len(set(portfolio[i]) & set(portfolio[j]))
            overlaps.append(overlap)
    
    return {
        'total_tickets': len(portfolio),
        'unique_numbers': len(all_numbers),
        'coverage_pct': len(all_numbers) / 50 * 100,
        'avg_overlap': np.mean(overlaps) if overlaps else 0,
        'max_overlap': max(overlaps) if overlaps else 0,
        'min_overlap': min(overlaps) if overlaps else 0
    }