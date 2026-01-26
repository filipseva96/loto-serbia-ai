"""
Consolidated models for ticket generation
Production-ready with adaptive learning
"""
import numpy as np
import pandas as pd
from lotto_ai.config import logger

# ============================================
# FREQUENCY MODEL
# ============================================
def frequency_probability(features, smoothing=1.0):
    """
    Calculate probability using Laplace smoothing
    
    P(number) = (hits + α) / (total_draws + α * n_numbers)
    """
    grouped = features.groupby("number")["hit"].agg(["sum", "count"])
    n_numbers = len(grouped)
    
    # Laplace smoothing
    grouped["freq_prob"] = (
        (grouped["sum"] + smoothing) /
        (grouped["count"] + smoothing * n_numbers)
    )
    
    return grouped["freq_prob"]

# ============================================
# TICKET GENERATION
# ============================================
def generate_ticket_safe(probs, n_numbers=7, max_attempts=100):
    """
    Generate a single ticket from probability distribution
    """
    numbers = probs.index.values
    probs_array = probs.values.astype(float)
    
    # Numerical safety
    probs_array = np.clip(probs_array, 1e-10, None)
    probs_array = probs_array / probs_array.sum()
    
    for attempt in range(max_attempts):
        try:
            ticket = np.random.choice(
                numbers,
                size=n_numbers,
                replace=False,
                p=probs_array
            )
            ticket = sorted(ticket.tolist())
            
            # Basic balance check
            odd_count = sum(n % 2 for n in ticket)
            if 2 <= odd_count <= 5:
                return ticket
        except Exception as e:
            logger.warning(f"Ticket generation attempt {attempt} failed: {e}")
            continue
    
    # Fallback: return anyway
    return ticket

# ============================================
# PORTFOLIO GENERATION
# ============================================
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
    from lotto_ai.core.learner import AdaptiveLearner
    
    portfolio = []
    
    # Get adaptive weights if enabled
    if use_adaptive:
        try:
            learner = AdaptiveLearner()
            weights = learner.get_current_weights('hybrid_v1')
            freq_ratio = weights.get('frequency_ratio', {}).get('value', 0.70)
            random_ratio = weights.get('random_ratio', {}).get('value', 0.30)
            logger.info(f"Using adaptive weights: {freq_ratio:.0%} freq / {random_ratio:.0%} random")
        except Exception as e:
            logger.warning(f"Failed to get adaptive weights, using defaults: {e}")
            freq_ratio = 0.70
            random_ratio = 0.30
    else:
        freq_ratio = 0.70
        random_ratio = 0.30
        logger.info(f"Using default weights: {freq_ratio:.0%} freq / {random_ratio:.0%} random")
    
    # Calculate number of each ticket type
    n_freq = int(n_tickets * freq_ratio)
    n_random = n_tickets - n_freq
    
    # Generate frequency-based tickets
    try:
        freq_probs = frequency_probability(features, smoothing=1.0)
        for i in range(n_freq):
            ticket = generate_ticket_safe(freq_probs)
            portfolio.append(ticket)
    except Exception as e:
        logger.error(f"Error generating frequency tickets: {e}")
        # Fallback to random
        n_random += n_freq
        n_freq = 0
    
    # Generate random tickets
    for i in range(n_random):
        try:
            ticket = sorted(np.random.choice(range(1, 51), 7, replace=False).tolist())
            
            # Basic balance check
            odd_count = sum(n % 2 for n in ticket)
            if 2 <= odd_count <= 5:
                portfolio.append(ticket)
            else:
                # Retry once
                ticket = sorted(np.random.choice(range(1, 51), 7, replace=False).tolist())
                portfolio.append(ticket)
        except Exception as e:
            logger.error(f"Error generating random ticket: {e}")
            continue
    
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
    
    # Overlap analysis
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