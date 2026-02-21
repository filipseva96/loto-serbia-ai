"""
Production model for Loto Serbia - v3.0
"""
import numpy as np
import random
from lotto_ai.config import (
    MIN_NUMBER, MAX_NUMBER, NUMBERS_PER_DRAW, NUMBER_RANGE, logger
)
from lotto_ai.core.coverage_optimizer import (
    optimize_portfolio_coverage,
    generate_random_portfolio
)


def generate_adaptive_portfolio(features, n_tickets=10, use_adaptive=True,
                                 strategy='coverage_optimized'):
    """
    Generate a portfolio of lottery tickets.

    Strategies:
      - 'coverage_optimized': Maximize pair/triple coverage (DEFAULT)
      - 'pure_random': Completely random (baseline)
      - 'hybrid': Mix of coverage-optimized and random
    """
    if strategy == 'pure_random' or not use_adaptive:
        portfolio, stats = generate_random_portfolio(n_tickets)
        metadata = {
            'strategy': 'pure_random',
            'n_tickets': n_tickets,
            'coverage_stats': _serialize_stats(stats),
            'n_freq_tickets': 0,
            'n_random_tickets': n_tickets,
            'frequency_ratio': 0.0,
            'random_ratio': 1.0
        }
        return portfolio, metadata

    elif strategy == 'coverage_optimized':
        portfolio, stats = optimize_portfolio_coverage(n_tickets)
        metadata = {
            'strategy': 'coverage_optimized',
            'n_tickets': n_tickets,
            'coverage_stats': _serialize_stats(stats),
            'n_freq_tickets': n_tickets,
            'n_random_tickets': 0,
            'frequency_ratio': 1.0,
            'random_ratio': 0.0,
            'pair_coverage_pct': stats['pair_coverage_pct'],
        }
        return portfolio, metadata

    else:  # hybrid
        n_optimized = max(1, int(n_tickets * 0.7))
        n_random = n_tickets - n_optimized

        optimized, opt_stats = optimize_portfolio_coverage(n_optimized)
        random_tickets, rnd_stats = generate_random_portfolio(n_random)

        portfolio = optimized + random_tickets

        metadata = {
            'strategy': 'hybrid',
            'n_tickets': n_tickets,
            'n_freq_tickets': n_optimized,
            'n_random_tickets': n_random,
            'frequency_ratio': n_optimized / n_tickets,
            'random_ratio': n_random / n_tickets,
        }
        return portfolio, metadata


def _serialize_stats(stats):
    """Make stats JSON-serializable"""
    serializable = {}
    for k, v in stats.items():
        if isinstance(v, (np.integer, np.int64)):
            serializable[k] = int(v)
        elif isinstance(v, (np.floating, np.float64)):
            serializable[k] = float(v)
        elif isinstance(v, tuple):
            serializable[k] = list(v)
        elif isinstance(v, np.ndarray):
            serializable[k] = v.tolist()
        else:
            serializable[k] = v
    return serializable


def portfolio_statistics(portfolio):
    """Calculate portfolio quality metrics"""
    import itertools
    from collections import Counter

    all_numbers = set()
    for ticket in portfolio:
        all_numbers.update(ticket)

    overlaps = []
    for i in range(len(portfolio)):
        for j in range(i + 1, len(portfolio)):
            overlap = len(set(portfolio[i]) & set(portfolio[j]))
            overlaps.append(overlap)

    covered_pairs = set()
    for ticket in portfolio:
        for i in range(len(ticket)):
            for j in range(i + 1, len(ticket)):
                covered_pairs.add((ticket[i], ticket[j]))

    total_pairs = 0
    for i in range(MIN_NUMBER, MAX_NUMBER + 1):
        for j in range(i + 1, MAX_NUMBER + 1):
            total_pairs += 1

    number_freq = Counter()
    for ticket in portfolio:
        for n in ticket:
            number_freq[n] += 1

    freq_vals = list(number_freq.values()) if number_freq else [0]

    return {
        'total_tickets': len(portfolio),
        'unique_numbers': len(all_numbers),
        'coverage_pct': len(all_numbers) / MAX_NUMBER * 100,
        'pair_coverage': len(covered_pairs),
        'pair_coverage_pct': (len(covered_pairs) / total_pairs * 100
                              if total_pairs > 0 else 0),
        'avg_overlap': float(np.mean(overlaps)) if overlaps else 0,
        'max_overlap': max(overlaps) if overlaps else 0,
        'min_overlap': min(overlaps) if overlaps else 0,
    }


def generate_ticket_safe(probs, n_numbers=NUMBERS_PER_DRAW, max_attempts=100):
    """Generate a single ticket from probability distribution (backward compat)"""
    numbers = probs.index.values
    probs_array = probs.values.astype(float)
    probs_array = np.clip(probs_array, 1e-10, None)
    probs_array = probs_array / probs_array.sum()

    for _ in range(max_attempts):
        try:
            ticket = np.random.choice(
                numbers, size=n_numbers, replace=False, p=probs_array
            )
            return sorted(ticket.tolist())
        except Exception:
            continue

    return sorted(random.sample(range(MIN_NUMBER, MAX_NUMBER + 1), n_numbers))


def frequency_probability(features, smoothing=1.0):
    """Frequency probability (descriptive, backward compat)"""
    grouped = features.groupby("number")["hit"].agg(["sum", "count"])
    n_numbers = len(grouped)
    grouped["freq_prob"] = (
        (grouped["sum"] + smoothing) /
        (grouped["count"] + smoothing * n_numbers)
    )
    return grouped["freq_prob"]