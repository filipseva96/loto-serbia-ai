"""
Combinatorial coverage optimizer for lottery portfolios.
Maximizes pair/triple coverage across tickets.
This is mathematically legitimate optimization.
"""
import numpy as np
import random
import itertools
from collections import Counter
from lotto_ai.config import (
    MIN_NUMBER, MAX_NUMBER, NUMBERS_PER_DRAW, logger
)


def optimize_portfolio_coverage(n_tickets, n_numbers=NUMBERS_PER_DRAW,
                                 min_num=MIN_NUMBER, max_num=MAX_NUMBER,
                                 monte_carlo_samples=None):
    """
    Generate tickets that MINIMIZE overlap and MAXIMIZE number pair coverage.

    Uses greedy set-cover with Monte Carlo candidate sampling.

    Args:
        n_tickets: Number of tickets to generate
        n_numbers: Numbers per ticket (7)
        min_num: Minimum number (1)
        max_num: Maximum number (39)
        monte_carlo_samples: Candidates evaluated per greedy step

    Returns:
        portfolio: List of sorted ticket lists
        coverage_stats: dict of coverage statistics
    """
    if monte_carlo_samples is None:
        monte_carlo_samples = 1500

    all_numbers = list(range(min_num, max_num + 1))
    portfolio = []
    covered_pairs = set()
    covered_triples = set()

    total_possible_pairs = 0
    for i in range(min_num, max_num + 1):
        for j in range(i + 1, max_num + 1):
            total_possible_pairs += 1

    logger.debug(f"Coverage optimizer: {n_tickets} tickets, "
                 f"{total_possible_pairs} possible pairs")

    for ticket_idx in range(n_tickets):
        best_ticket = None
        best_score = -1

        for _ in range(monte_carlo_samples):
            candidate = sorted(random.sample(all_numbers, n_numbers))

            # Calculate pairs this candidate covers
            candidate_pairs = set()
            for i in range(len(candidate)):
                for j in range(i + 1, len(candidate)):
                    candidate_pairs.add((candidate[i], candidate[j]))

            # Calculate triples
            candidate_triples = set()
            for i in range(len(candidate)):
                for j in range(i + 1, len(candidate)):
                    for k in range(j + 1, len(candidate)):
                        candidate_triples.add(
                            (candidate[i], candidate[j], candidate[k])
                        )

            new_pairs = len(candidate_pairs - covered_pairs)
            new_triples = len(candidate_triples - covered_triples)

            # Penalize heavy overlap with existing tickets
            overlap_penalty = 0
            for existing in portfolio:
                overlap = len(set(candidate) & set(existing))
                if overlap >= 5:
                    overlap_penalty += (overlap - 4) * 3

            score = new_pairs + 0.3 * new_triples - overlap_penalty

            # Balance: prefer 2-5 odd numbers
            odd_count = sum(1 for n in candidate if n % 2 == 1)
            if not (2 <= odd_count <= 5):
                score -= 5

            # Sum range: avoid extreme sums
            ticket_sum = sum(candidate)
            expected_sum = n_numbers * (min_num + max_num) / 2
            sum_deviation = abs(ticket_sum - expected_sum) / expected_sum
            if sum_deviation > 0.3:
                score -= 3

            if score > best_score:
                best_score = score
                best_ticket = candidate

        if best_ticket is None:
            best_ticket = sorted(random.sample(all_numbers, n_numbers))

        portfolio.append(best_ticket)

        # Update covered sets
        for i in range(len(best_ticket)):
            for j in range(i + 1, len(best_ticket)):
                covered_pairs.add((best_ticket[i], best_ticket[j]))
                for k in range(j + 1, len(best_ticket)):
                    covered_triples.add(
                        (best_ticket[i], best_ticket[j], best_ticket[k])
                    )

        logger.debug(f"Ticket {ticket_idx + 1}: {best_ticket} | "
                     f"Pairs covered: {len(covered_pairs)}/{total_possible_pairs}")

    coverage_stats = _calculate_coverage_stats(
        portfolio, covered_pairs, covered_triples,
        total_possible_pairs, max_num
    )

    logger.info(f"Generated {n_tickets} coverage-optimized tickets | "
                f"Pair coverage: {coverage_stats['pair_coverage_pct']:.1f}%")

    return portfolio, coverage_stats


def _calculate_coverage_stats(portfolio, covered_pairs, covered_triples,
                               total_possible_pairs, max_num):
    """Calculate detailed coverage statistics"""
    all_numbers_used = set()
    for ticket in portfolio:
        all_numbers_used.update(ticket)

    overlaps = []
    for i in range(len(portfolio)):
        for j in range(i + 1, len(portfolio)):
            overlap = len(set(portfolio[i]) & set(portfolio[j]))
            overlaps.append(overlap)

    number_freq = Counter()
    for ticket in portfolio:
        for n in ticket:
            number_freq[n] += 1

    freq_values = list(number_freq.values()) if number_freq else [0]

    most_common = number_freq.most_common(1)
    least_common = number_freq.most_common()[-1:] if number_freq else []

    return {
        'total_tickets': len(portfolio),
        'unique_numbers': len(all_numbers_used),
        'number_coverage_pct': len(all_numbers_used) / max_num * 100,
        'pairs_covered': len(covered_pairs),
        'pairs_total': total_possible_pairs,
        'pair_coverage_pct': (len(covered_pairs) / total_possible_pairs * 100
                              if total_possible_pairs > 0 else 0),
        'triples_covered': len(covered_triples),
        'avg_overlap': float(np.mean(overlaps)) if overlaps else 0.0,
        'max_overlap': max(overlaps) if overlaps else 0,
        'min_overlap': min(overlaps) if overlaps else 0,
        'number_freq_std': float(np.std(freq_values)),
        'most_used_number': most_common[0] if most_common else (0, 0),
        'least_used_number': least_common[0] if least_common else (0, 0),
    }


def generate_random_portfolio(n_tickets, n_numbers=NUMBERS_PER_DRAW,
                               min_num=MIN_NUMBER, max_num=MAX_NUMBER):
    """Generate purely random portfolio for baseline comparison"""
    all_numbers = list(range(min_num, max_num + 1))
    portfolio = []

    for _ in range(n_tickets):
        ticket = sorted(random.sample(all_numbers, n_numbers))
        portfolio.append(ticket)

    covered_pairs = set()
    covered_triples = set()
    for ticket in portfolio:
        for i in range(len(ticket)):
            for j in range(i + 1, len(ticket)):
                covered_pairs.add((ticket[i], ticket[j]))
                for k in range(j + 1, len(ticket)):
                    covered_triples.add((ticket[i], ticket[j], ticket[k]))

    total_possible_pairs = 0
    for i in range(min_num, max_num + 1):
        for j in range(i + 1, max_num + 1):
            total_possible_pairs += 1

    coverage_stats = _calculate_coverage_stats(
        portfolio, covered_pairs, covered_triples,
        total_possible_pairs, max_num
    )

    return portfolio, coverage_stats