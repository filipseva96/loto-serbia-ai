"""
Core mathematical engine for lottery analysis.
All computations are exact and rigorous.
"""
import numpy as np
from math import comb
from scipy import stats as scipy_stats
from collections import Counter
import itertools
from lotto_ai.config import (
    MIN_NUMBER, MAX_NUMBER, NUMBERS_PER_DRAW,
    TOTAL_COMBINATIONS, PRIZE_TABLE, TICKET_COST, logger
)


def match_probability(k, n_pool=MAX_NUMBER, n_draw=NUMBERS_PER_DRAW):
    """
    Exact probability of matching exactly k numbers.
    Hypergeometric distribution.
    """
    if k < 0 or k > n_draw:
        return 0.0
    remaining = n_pool - n_draw
    needed_from_remaining = n_draw - k
    if needed_from_remaining < 0 or needed_from_remaining > remaining:
        return 0.0
    numerator = comb(n_draw, k) * comb(remaining, needed_from_remaining)
    denominator = comb(n_pool, n_draw)
    return numerator / denominator


def match_probability_at_least(k, n_pool=MAX_NUMBER, n_draw=NUMBERS_PER_DRAW):
    """Probability of matching at least k numbers"""
    total = 0.0
    for i in range(k, n_draw + 1):
        total += match_probability(i, n_pool, n_draw)
    return total


def expected_value_per_ticket(prize_table=None, ticket_cost=None):
    """Calculate exact expected value per ticket"""
    if prize_table is None:
        prize_table = PRIZE_TABLE
    if ticket_cost is None:
        ticket_cost = TICKET_COST

    ev = 0.0
    breakdown = {}

    for matches, prize in prize_table.items():
        p = match_probability(matches)
        contribution = p * prize
        ev += contribution
        breakdown[matches] = {
            'probability': p,
            'prize': prize,
            'expected_contribution': contribution,
            'odds': f"1 in {int(1/p):,}" if p > 0 else "impossible"
        }

    roi = ((ev - ticket_cost) / ticket_cost) * 100 if ticket_cost > 0 else 0

    return {
        'expected_value': ev,
        'ticket_cost': ticket_cost,
        'net_ev': ev - ticket_cost,
        'roi_percent': roi,
        'breakdown': breakdown
    }


def portfolio_expected_value(n_tickets, prize_table=None, ticket_cost=None):
    """Expected value for a portfolio of n independent tickets"""
    single = expected_value_per_ticket(prize_table, ticket_cost)
    if ticket_cost is None:
        ticket_cost = TICKET_COST

    total_cost = n_tickets * ticket_cost
    total_ev = n_tickets * single['expected_value']

    p_miss_3plus = (1 - match_probability_at_least(3)) ** n_tickets
    p_at_least_one_3plus = 1 - p_miss_3plus

    p_miss_4plus = (1 - match_probability_at_least(4)) ** n_tickets
    p_miss_5plus = (1 - match_probability_at_least(5)) ** n_tickets

    return {
        'n_tickets': n_tickets,
        'total_cost': total_cost,
        'total_ev': total_ev,
        'net_ev': total_ev - total_cost,
        'roi_percent': ((total_ev - total_cost) / total_cost * 100
                        if total_cost > 0 else 0),
        'prob_any_3plus': p_at_least_one_3plus,
        'prob_any_4plus': 1 - p_miss_4plus,
        'prob_any_5plus': 1 - p_miss_5plus,
    }


def test_lottery_fairness(draws_df):
    """
    Run rigorous statistical tests on historical draws.
    """
    all_numbers = []
    for _, row in draws_df.iterrows():
        for i in range(1, NUMBERS_PER_DRAW + 1):
            col = f'n{i}'
            if col in draws_df.columns:
                all_numbers.append(int(row[col]))

    n_draws = len(draws_df)
    results = {
        'n_draws': n_draws,
        'n_total_numbers': len(all_numbers)
    }

    # TEST 1: Chi-Square for individual number uniformity
    observed = np.zeros(MAX_NUMBER)
    for n in all_numbers:
        if 1 <= n <= MAX_NUMBER:
            observed[n - 1] += 1

    # Expected must sum to exactly the same as observed
    total_obs = float(observed.sum())
    expected_arr = np.full(MAX_NUMBER, total_obs / MAX_NUMBER)

    chi2_stat, chi2_p = scipy_stats.chisquare(observed, expected_arr)

    results['chi_square'] = {
        'statistic': float(chi2_stat),
        'p_value': float(chi2_p),
        'degrees_of_freedom': MAX_NUMBER - 1,
        'conclusion': ('FAIR (no significant deviation from uniform)'
                       if chi2_p > 0.05
                       else 'SUSPICIOUS (significant deviation detected)'),
        'is_fair': chi2_p > 0.05,
        'expected_count': total_obs / MAX_NUMBER
    }

    # TEST 2: Runs Test
    runs_results = []
    for num in range(MIN_NUMBER, MAX_NUMBER + 1):
        sequence = []
        for _, row in draws_df.iterrows():
            drawn = [int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)]
            sequence.append(1 if num in drawn else 0)

        if len(sequence) >= 20:
            n1 = sum(sequence)
            n0 = len(sequence) - n1
            if n1 > 0 and n0 > 0:
                runs = 1
                for j in range(1, len(sequence)):
                    if sequence[j] != sequence[j - 1]:
                        runs += 1

                expected_runs = (2 * n0 * n1) / (n0 + n1) + 1
                denom = (n0 + n1) ** 2 * (n0 + n1 - 1)
                if denom > 0:
                    var_runs = (2 * n0 * n1 * (2 * n0 * n1 - n0 - n1)) / denom
                else:
                    var_runs = 0

                if var_runs > 0:
                    z = (runs - expected_runs) / np.sqrt(var_runs)
                    p = 2 * (1 - scipy_stats.norm.cdf(abs(z)))
                    runs_results.append({
                        'number': num,
                        'z_score': float(z),
                        'p_value': float(p),
                        'is_random': p > 0.05
                    })

    n_non_random = sum(1 for r in runs_results if not r['is_random'])
    expected_false_positives = len(runs_results) * 0.05

    results['runs_test'] = {
        'n_numbers_tested': len(runs_results),
        'n_non_random': n_non_random,
        'expected_false_positives': expected_false_positives,
        'conclusion': ('FAIR (non-random count within expected range)'
                       if n_non_random <= expected_false_positives * 2
                       else 'SUSPICIOUS (more non-random than expected)'),
        'is_fair': n_non_random <= expected_false_positives * 2
    }

    # TEST 3: Serial Correlation
    draw_sums = []
    for _, row in draws_df.iterrows():
        s = sum(int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1))
        draw_sums.append(s)

    if len(draw_sums) >= 10:
        corr_matrix = np.corrcoef(draw_sums[:-1], draw_sums[1:])
        correlation = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0

        n_corr = len(draw_sums) - 1
        if abs(correlation) < 1 and n_corr > 2:
            t_stat = correlation * np.sqrt(n_corr - 2) / np.sqrt(1 - correlation ** 2)
            p_value = float(2 * (1 - scipy_stats.t.cdf(abs(t_stat), n_corr - 2)))
        else:
            t_stat = 0.0
            p_value = 1.0

        results['serial_correlation'] = {
            'correlation': correlation,
            't_statistic': float(t_stat),
            'p_value': p_value,
            'conclusion': ('FAIR (no serial correlation)'
                           if p_value > 0.05
                           else 'SUSPICIOUS (serial correlation detected)'),
            'is_fair': p_value > 0.05
        }
    else:
        results['serial_correlation'] = {
            'correlation': 0.0,
            'conclusion': 'INSUFFICIENT DATA',
            'is_fair': True
        }

    # TEST 4: Pair Frequency
    pair_counts = Counter()
    for _, row in draws_df.iterrows():
        drawn = sorted([int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)])
        for pair in itertools.combinations(drawn, 2):
            pair_counts[pair] += 1

    n_possible_pairs = comb(MAX_NUMBER, 2)

    if n_possible_pairs > 0 and n_draws >= 50:
        pair_observed = []
        for i in range(MIN_NUMBER, MAX_NUMBER + 1):
            for j in range(i + 1, MAX_NUMBER + 1):
                pair_observed.append(pair_counts.get((i, j), 0))

        pair_observed = np.array(pair_observed, dtype=float)
        total_pair_obs = float(pair_observed.sum())

        # CRITICAL: expected must sum to exactly the same as observed
        pair_expected = np.full(len(pair_observed), total_pair_obs / len(pair_observed))

        try:
            pair_chi2, pair_p = scipy_stats.chisquare(pair_observed, pair_expected)
            results['pair_test'] = {
                'chi_square': float(pair_chi2),
                'p_value': float(pair_p),
                'expected_pair_frequency': float(total_pair_obs / len(pair_observed)),
                'conclusion': ('FAIR (pairs uniformly distributed)'
                               if pair_p > 0.05
                               else 'SUSPICIOUS (pair frequency anomaly)'),
                'is_fair': pair_p > 0.05
            }
        except ValueError as ve:
            logger.warning(f"Pair chi-square failed: {ve}")
            results['pair_test'] = {
                'conclusion': f'TEST SKIPPED ({str(ve)})',
                'is_fair': True
            }
    else:
        results['pair_test'] = {
            'conclusion': 'INSUFFICIENT DATA (need 50+ draws)',
            'is_fair': True
        }

    # OVERALL
    tests = ['chi_square', 'runs_test', 'serial_correlation', 'pair_test']
    n_fair = sum(1 for t in tests if results.get(t, {}).get('is_fair', True))

    results['overall'] = {
        'tests_passed': n_fair,
        'tests_total': len(tests),
        'conclusion': ('LOTTERY APPEARS FAIR - No exploitable patterns detected'
                       if n_fair >= 3
                       else 'SOME ANOMALIES - May warrant investigation'),
        'is_fair': n_fair >= 3,
        'recommendation': ('Portfolio optimization (coverage/wheeling) is the best strategy'
                           if n_fair >= 3
                           else 'Anomalies found but likely insufficient for exploitation')
    }

    return results


def number_statistics(draws_df):
    """Descriptive statistics for each number (NOT predictive)"""
    n_draws = len(draws_df)
    if n_draws == 0:
        return {}

    stats = {}
    expected_freq = NUMBERS_PER_DRAW / MAX_NUMBER

    for num in range(MIN_NUMBER, MAX_NUMBER + 1):
        appearances = 0
        last_seen = None

        for idx in range(n_draws):
            row = draws_df.iloc[idx]
            drawn = [int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)]
            if num in drawn:
                appearances += 1
                last_seen = idx

        current_gap = (n_draws - 1 - last_seen) if last_seen is not None else n_draws
        freq = appearances / n_draws

        stats[num] = {
            'appearances': appearances,
            'frequency': freq,
            'expected_frequency': expected_freq,
            'deviation_from_expected': freq - expected_freq,
            'current_gap': current_gap,
        }

    return stats


def kelly_criterion_lottery(bankroll, prize_table=None, ticket_cost=None):
    """Kelly criterion for lottery - always says don't bet on negative EV"""
    ev_data = expected_value_per_ticket(prize_table, ticket_cost)
    if ticket_cost is None:
        ticket_cost = TICKET_COST

    edge = (ev_data['expected_value'] - ticket_cost) / ticket_cost if ticket_cost > 0 else -1
    kelly_fraction = max(0.0, edge)

    entertainment_budget = bankroll * 0.01
    max_tickets = max(1, int(entertainment_budget / ticket_cost)) if ticket_cost > 0 else 1

    return {
        'kelly_fraction': kelly_fraction,
        'kelly_says': ('DO NOT BET (negative expected value)'
                       if kelly_fraction == 0
                       else f'Bet {kelly_fraction:.4%} of bankroll'),
        'edge': edge,
        'entertainment_budget': entertainment_budget,
        'max_responsible_tickets': max_tickets,
        'recommendation': (
            f'Treat as entertainment. Max {max_tickets} tickets '
            f'({entertainment_budget:.0f} RSD) from {bankroll:.0f} RSD bankroll.'
        )
    }