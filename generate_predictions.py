"""
Generate predictions and save them for tracking
Uses coverage-optimized portfolio generation
"""
from datetime import datetime, timedelta
from lotto_ai.features.features import build_feature_matrix, load_draws
from lotto_ai.core.models import generate_optimized_portfolio
from lotto_ai.core.coverage_optimizer import portfolio_statistics
from lotto_ai.core.tracker import PredictionTracker
from lotto_ai.core.learner import AdaptiveLearner
from lotto_ai.config import DRAW_DAYS, logger


def get_next_draw_date():
    """Calculate next draw date using configured DRAW_DAYS"""
    today = datetime.now()
    days_ahead = 0

    while True:
        days_ahead += 1
        next_date = today + timedelta(days=days_ahead)
        if next_date.weekday() in DRAW_DAYS:
            return next_date.strftime('%Y-%m-%d')


def main():
    print("=" * 70)
    print("🎰 LOTO SRBIJA - SMART PORTFOLIO OPTIMIZER")
    print("=" * 70)

    tracker = PredictionTracker()
    learner = AdaptiveLearner()

    # Step 1: Auto-evaluate pending
    print("\n📊 Korak 1: Provera prethodnih predviđanja...")
    evaluated = tracker.auto_evaluate_pending()
    if evaluated > 0:
        print(f"   ✅ Evaluirano {evaluated} predviđanja")

    # Step 2: Track performance
    print("\n📈 Korak 2: Praćenje performansi...")
    tracking = learner.update_weights(strategy_name='coverage_v3', window=20)
    if tracking:
        print(f"   {tracking['interpretation']}")

    # Step 3: Performance stats
    print("\n📊 Korak 3: Trenutne performanse:")
    perf = tracker.get_strategy_performance(window=50)
    if perf:
        print(f"   Poslednjih {perf['n_predictions']} predviđanja:")
        print(f"   • Prosečno pogodaka: {perf['avg_best_match']:.2f}/7")
        print(f"   • Prosečna nagrada: {perf['avg_prize_value']:.2f} RSD")
        print(f"   • Stopa pogotka (3+): {perf['hit_rate_3plus']:.1%}")
        print(f"   • Najbolje ikad: {perf['best_ever']}/7")
        print(f"   • Ukupno osvojeno: {perf['total_prize_won']:,.0f} RSD")
    else:
        print("   Nema istorijskih podataka")

    # Step 4: Generate portfolio
    print("\n🎯 Korak 4: Generisanje coverage-optimized portfolia...")
    portfolio, metadata = generate_optimized_portfolio(
        n_tickets=10,
        strategy='balanced'
    )

    # Step 5: Save prediction
    next_draw = get_next_draw_date()
    print(f"\n💾 Korak 5: Čuvanje predviđanja za {next_draw}...")

    prediction_id = tracker.save_prediction(
        target_draw_date=next_draw,
        strategy_name='coverage_v3',
        tickets=portfolio,
        model_version='3.0_coverage_optimizer',
        metadata=metadata
    )

    # Step 6: Display
    stats = portfolio_statistics(portfolio)

    print("\n" + "=" * 70)
    print("📦 PORTFOLIO STATISTIKE")
    print("=" * 70)
    print(f"  ID Predviđanja:     {prediction_id}")
    print(f"  Ciljno izvlačenje:  {next_draw}")
    print(f"  Ukupno tiketa:      {stats['total_tickets']}")
    print(f"  Jedinstveni brojevi: {stats['unique_numbers']}/39 ({stats['number_coverage_pct']:.1f}%)")
    print(f"  Pokrivenost parova: {stats['pair_coverage_pct']:.1f}%")
    print(f"  Prosečno preklapanje: {stats['avg_overlap']:.2f}")
    print(f"  Skor raznovrsnosti: {stats['diversity_score']:.3f}")
    print(f"  P(bar 1 tiket 3+): {stats['p_at_least_one_3plus']:.1%}")

    print("\n" + "=" * 70)
    print("🎟️  VAŠI TIKETI (Coverage-Optimized)")
    print("=" * 70)

    for i, ticket in enumerate(portfolio, 1):
        ticket_str = ' '.join(f'{n:2d}' for n in ticket)
        print(f"  Tiket {i:2d}: [{ticket_str}]")

    print("\n" + "=" * 70)
    print("📝 SLEDEĆI KORACI")
    print("=" * 70)
    print(f"""
  1. Odigrajte izabrane tikete za {next_draw}
  2. Posle izvlačenja, pokrenite ponovo za:
     • Evaluaciju predviđanja
     • Ažuriranje statistika
     • Generisanje novih tiketa

  ⚠️  NAPOMENA: Ovi tiketi su COVERAGE-OPTIMIZED.
  To znači da pokrivaju što više kombinacija,
  ali svaki tiket ima ISTU šansu kao nasumičan.
  Igrajte odgovorno!
    """)
    print("=" * 70)


if __name__ == "__main__":
    main()