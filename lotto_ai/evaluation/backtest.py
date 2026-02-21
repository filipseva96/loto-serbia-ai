"""
Backtest evaluation - honest comparison against random baseline
"""
import numpy as np
from datetime import datetime
from lotto_ai.core.db import get_session, Draw
from lotto_ai.core.coverage_optimizer import CoverageOptimizer
from lotto_ai.config import (
    logger, NUMBER_RANGE, NUMBERS_PER_DRAW, MAX_NUMBER,
    MIN_NUMBER, MATCH_PROBABILITIES, PRIZE_TABLE, TICKET_COST
)


def main():
    """Run honest backtest comparing coverage-optimized vs random portfolios"""
    print("=" * 70)
    print("📊 HONEST BACKTEST: Coverage-Optimized vs Pure Random")
    print("=" * 70)

    session = get_session()
    draws = session.query(Draw).order_by(Draw.draw_date).all()
    session.close()

    if len(draws) < 30:
        print(f"❌ Need at least 30 draws for backtest, have {len(draws)}")
        return

    n_test_draws = min(100, len(draws) - 10)
    test_draws = draws[-n_test_draws:]
    n_tickets_per_draw = 6

    print(f"\n📋 Configuration:")
    print(f"   Test draws: {n_test_draws}")
    print(f"   Tickets per draw: {n_tickets_per_draw}")
    print(f"   Strategy A: Coverage-Optimized (balanced)")
    print(f"   Strategy B: Pure Random")
    print()

    rng = np.random.default_rng(42)
    all_numbers = list(range(MIN_NUMBER, MAX_NUMBER + 1))

    results_coverage = {'matches': [], 'prizes': []}
    results_random = {'matches': [], 'prizes': []}

    for i, draw in enumerate(test_draws):
        actual = set(draw.get_numbers())

        # Strategy A: Coverage-optimized
        optimizer = CoverageOptimizer(rng_seed=42 + i)
        portfolio_coverage = optimizer.generate_balanced_portfolio(n_tickets_per_draw)

        best_match_cov = 0
        total_prize_cov = 0
        for ticket in portfolio_coverage:
            matches = len(set(ticket) & actual)
            best_match_cov = max(best_match_cov, matches)
            total_prize_cov += PRIZE_TABLE.get(matches, 0)

        results_coverage['matches'].append(best_match_cov)
        results_coverage['prizes'].append(total_prize_cov)

        # Strategy B: Pure random
        best_match_rand = 0
        total_prize_rand = 0
        for _ in range(n_tickets_per_draw):
            ticket = sorted(rng.choice(all_numbers, size=NUMBERS_PER_DRAW, replace=False))
            matches = len(set(ticket) & actual)
            best_match_rand = max(best_match_rand, matches)
            total_prize_rand += PRIZE_TABLE.get(matches, 0)

        results_random['matches'].append(best_match_rand)
        results_random['prizes'].append(total_prize_rand)

        if (i + 1) % 20 == 0:
            print(f"   Processed {i + 1}/{n_test_draws} draws...")

    # Results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)

    total_cost = n_test_draws * n_tickets_per_draw * TICKET_COST

    for name, results in [("Coverage-Optimized", results_coverage),
                           ("Pure Random", results_random)]:
        matches = results['matches']
        prizes = results['prizes']

        print(f"\n{'=' * 50}")
        print(f"  {name}")
        print(f"{'=' * 50}")
        print(f"  Avg best match:  {np.mean(matches):.3f}/7")
        print(f"  Best match ever: {max(matches)}/7")
        print(f"  3+ match rate:   {sum(1 for m in matches if m >= 3) / len(matches):.1%}")
        print(f"  4+ match rate:   {sum(1 for m in matches if m >= 4) / len(matches):.1%}")
        print(f"  Total prizes:    {sum(prizes):,} RSD")
        print(f"  Total cost:      {total_cost:,} RSD")
        print(f"  Net result:      {sum(prizes) - total_cost:,} RSD")
        print(f"  ROI:             {(sum(prizes) - total_cost) / total_cost * 100:.1f}%")

    # Statistical comparison
    from scipy import stats
    t_stat, p_value = stats.ttest_ind(
        results_coverage['matches'], results_random['matches']
    )

    print(f"\n{'=' * 50}")
    print(f"  Statistical Comparison")
    print(f"{'=' * 50}")
    print(f"  T-statistic:   {t_stat:.4f}")
    print(f"  P-value:       {p_value:.4f}")

    if p_value < 0.05:
        if np.mean(results_coverage['matches']) > np.mean(results_random['matches']):
            print(f"  ✅ Coverage strategy is statistically better!")
        else:
            print(f"  ❌ Random is statistically better (unexpected)")
    else:
        print(f"  ➡️  No significant difference (as expected for fair lottery)")

    print(f"\n💡 Coverage optimization doesn't change per-ticket probability,")
    print(f"   but maximizes PORTFOLIO diversity, reducing redundancy.")
    print("=" * 70)


if __name__ == "__main__":
    main()