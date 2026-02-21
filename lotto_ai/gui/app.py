"""
Streamlit UI for Loto Serbia - v3.0
Smart Portfolio Manager with honest mathematics
"""
import streamlit as st
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from lotto_ai.core.db import init_db, get_session, Draw, Prediction, PredictionResult
from lotto_ai.core.tracker import PredictionTracker, PlayedTicketsTracker
from lotto_ai.core.learner import AdaptiveLearner
from lotto_ai.core.models import generate_adaptive_portfolio, portfolio_statistics
from lotto_ai.core.math_engine import (
    expected_value_per_ticket, portfolio_expected_value,
    match_probability, match_probability_at_least,
    kelly_criterion_lottery, test_lottery_fairness
)
from lotto_ai.core.wheeling import (
    generate_abbreviated_wheel, wheel_cost_estimate
)
from lotto_ai.features.features import build_feature_matrix, load_draws, get_number_summary
from lotto_ai.config import (
    SCRAPING_ENABLED, IS_CLOUD, logger, DRAW_DAYS, DRAW_HOUR,
    NUMBERS_PER_DRAW, MAX_NUMBER, MIN_NUMBER, PRIZE_TABLE, TICKET_COST,
    TOTAL_COMBINATIONS
)
from math import comb
from datetime import datetime, timedelta

init_db()


def get_next_draw_info():
    now = datetime.now()
    current_hour = now.hour
    current_weekday = now.weekday()

    if current_weekday in DRAW_DAYS:
        if current_hour < DRAW_HOUR:
            hours_until = DRAW_HOUR - current_hour
            return now.strftime('%Y-%m-%d'), True, hours_until

    days_ahead = 1
    while days_ahead <= 7:
        next_date = now + timedelta(days=days_ahead)
        if next_date.weekday() in DRAW_DAYS:
            draw_datetime = next_date.replace(hour=DRAW_HOUR, minute=0, second=0)
            hours_until = (draw_datetime - now).total_seconds() / 3600
            return next_date.strftime('%Y-%m-%d'), False, hours_until
        days_ahead += 1

    return (now + timedelta(days=1)).strftime('%Y-%m-%d'), False, 24


def get_next_draw_date():
    draw_date, _, _ = get_next_draw_info()
    return draw_date


def format_draw_info_message(draw_date, is_today, hours_until):
    day_names = {
        0: 'Ponedeljak', 1: 'Utorak', 2: 'Sreda',
        3: 'Četvrtak', 4: 'Petak', 5: 'Subota', 6: 'Nedelja'
    }
    if is_today:
        if hours_until > 2:
            return f"🎯 **DANAŠNJE IZVLAČENJE** - {draw_date} u 21:00 (za ~{int(hours_until)}h)"
        else:
            return f"⚡ **DANAŠNJE IZVLAČENJE** - {draw_date} - USKORO!"
    else:
        days_until = max(1, int(hours_until / 24))
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_name = day_names.get(draw_dt.weekday(), draw_dt.strftime('%A'))
        return (f"📅 Sledeće izvlačenje: **{day_name}, {draw_date}** "
                f"(za {days_until} dan{'a' if days_until != 1 else ''})")


def check_password():
    def password_entered():
        try:
            correct_password = st.secrets.get("app_password", "gotovac71")
        except Exception:
            correct_password = "gotovac71"

        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔐 Loto Srbija - Prijava")
        st.text_input("Unesite lozinku", type="password",
                      on_change=password_entered, key="password")
        st.info("💡 Unesite lozinku za pristup")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Unesite lozinku", type="password",
                      on_change=password_entered, key="password")
        st.error("❌ Pogrešna lozinka")
        return False
    else:
        return True


if not check_password():
    st.stop()

st.set_page_config(
    page_title="Loto Srbija - Smart Portfolio",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #c9082a 0%, #17408b 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .ticket-box {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #c9082a;
        margin: 1rem 0;
    }
    .ticket-box.selected {
        background: #e3f2fd;
        border-left: 5px solid #17408b;
    }
    .number-ball {
        display: inline-block;
        background: linear-gradient(135deg, #c9082a 0%, #17408b 100%);
        color: white;
        font-weight: bold;
        font-size: 1.2rem;
        padding: 0.5rem 0.8rem;
        border-radius: 50%;
        margin: 0.2rem;
        min-width: 45px;
        text-align: center;
    }
    .math-box {
        background: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 0.5rem 0;
    }
    .honest-box {
        background: #f8d7da;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #dc3545;
        margin: 0.5rem 0;
    }
    .good-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎰 Loto Srbija - Smart Portfolio Manager</h1>
    <p style="font-size: 1.2rem; margin: 0;">
        Optimizovano Pokrivanje Brojeva sa Matematičkim Garancijama
    </p>
    <p style="font-size: 0.9rem; margin: 0; opacity: 0.9;">LOTO 7/39</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown("### ℹ️ Kako Radi")
    st.info("""
    🧮 **Matematički pristup:**

    1️⃣ **Optimizacija Pokrivanja** - Maksimizuje
    pokrivanje parova/trojki brojeva

    2️⃣ **Wheeling Sistem** - Matematičke
    garancije pogodaka

    3️⃣ **Analiza Fer Igre** - Testira da li
    je lutrija poštena

    4️⃣ **Odgovorno Igranje** - Bankroll
    upravljanje

    ⚠️ Lutrija ima negativan očekivani
    povraćaj. Igrajte odgovorno!
    """)

    st.markdown("---")
    st.markdown("### ⚙️ Navigacija")

    page = st.radio("📄 Stranica", [
        "🎲 Generator Tiketa",
        "🎯 Wheeling Sistem",
        "📊 Matematika",
        "🔬 Fer Igra Test",
        "📈 Istorija"
    ])

    st.markdown("---")
    st.markdown("### ⏰ Sledeće Izvlačenje")
    draw_date, is_today, hours_until = get_next_draw_info()

    if is_today:
        st.success("**DANAS** u 21:00")
        progress_val = max(0.0, min((21 - hours_until) / 21, 1.0))
        st.progress(progress_val)
        st.caption(f"~{int(hours_until)} sati preostalo")
    else:
        days_until = max(1, int(hours_until / 24))
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_names = {0: 'Ponedeljak', 1: 'Utorak', 2: 'Sreda',
                     3: 'Četvrtak', 4: 'Petak', 5: 'Subota', 6: 'Nedelja'}
        day_name = day_names.get(draw_dt.weekday(), '')
        st.info(f"**{day_name}**\n{draw_date}")
        st.caption(f"Za {days_until} dan{'a' if days_until != 1 else ''}")

    st.markdown("---")
    if st.button("🚪 Odjava"):
        st.session_state["password_correct"] = False
        st.rerun()

# ============================================================================
# PAGE: TICKET GENERATOR
# ============================================================================
if page == "🎲 Generator Tiketa":

    if 'generated_tickets' not in st.session_state:
        st.session_state.generated_tickets = None
    if 'selected_tickets' not in st.session_state:
        st.session_state.selected_tickets = []

    st.markdown("### 🎲 Coverage-Optimized Ticket Generator")

    st.markdown("""
    <div class="good-box">
    <strong>✅ Šta ovo radi:</strong> Generiše tikete koji pokrivaju MAKSIMALAN broj
    parova i trojki brojeva. Ovo matematički povećava verovatnoću da bar jedan tiket
    ima 3+ pogodaka u odnosu na nasumične tikete.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="honest-box">
    <strong>⚠️ Iskreno upozorenje:</strong> Nijedan metod ne može predvideti buduće
    izvlačenje. Svako izvlačenje je nezavisno. Ovo optimizuje POKRIVANJE, ne PREDIKCIJU.
    </div>
    """, unsafe_allow_html=True)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        n_tickets = st.slider("Broj tiketa", 3, 20, 7)
    with col_s2:
        strategy = st.selectbox("Strategija", [
            "coverage_optimized",
            "hybrid",
            "pure_random"
        ], format_func=lambda x: {
            'coverage_optimized': '🎯 Optimizovano Pokrivanje (preporučeno)',
            'hybrid': '🔄 Hibrid (pokrivanje + nasumično)',
            'pure_random': '🎲 Čisto Nasumično (za poređenje)'
        }[x])

    pev = portfolio_expected_value(n_tickets)
    col_ev1, col_ev2, col_ev3, col_ev4 = st.columns(4)
    col_ev1.metric("Ukupna Cena", f"{pev['total_cost']:,.0f} RSD")
    col_ev2.metric("Očekivani Povraćaj", f"{pev['total_ev']:,.1f} RSD")
    col_ev3.metric("ROI", f"{pev['roi_percent']:.1f}%")
    col_ev4.metric("Šansa za 3+", f"{pev['prob_any_3plus']:.1%}")

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        generate_clicked = st.button("🎲 GENERIŠI TIKETE", type="primary")

    if generate_clicked:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("📊 Evaluacija prethodnih predviđanja...")
            progress_bar.progress(20)
            tracker = PredictionTracker()
            tracker.auto_evaluate_pending()

            status_text.text("🧮 Optimizacija pokrivanja...")
            progress_bar.progress(40)
            features = build_feature_matrix()

            status_text.text("🎲 Generisanje tiketa...")
            progress_bar.progress(60)
            portfolio, weights = generate_adaptive_portfolio(
                features, n_tickets=n_tickets,
                use_adaptive=True, strategy=strategy
            )

            status_text.text("💾 Čuvanje...")
            progress_bar.progress(80)
            next_draw = get_next_draw_date()
            prediction_id = tracker.save_prediction(
                target_draw_date=next_draw,
                strategy_name=strategy,
                tickets=portfolio,
                model_version='3.0_coverage',
                metadata=weights
            )

            perf = tracker.get_strategy_performance(strategy, window=50)

            st.session_state.generated_tickets = portfolio
            st.session_state.prediction_id = prediction_id
            st.session_state.next_draw = next_draw
            st.session_state.selected_tickets = []
            st.session_state.weights = weights
            st.session_state.performance = perf
            st.session_state.current_strategy = strategy

            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()

            stats = portfolio_statistics(portfolio)
            st.success(f"✅ Generisano {len(portfolio)} tiketa!")
            st.info(f"📊 Pokrivanje parova: {stats['pair_coverage_pct']:.1f}% | "
                    f"Jedinstveni brojevi: {stats['unique_numbers']}/{MAX_NUMBER} | "
                    f"Prosečno preklapanje: {stats['avg_overlap']:.1f}")

            st.rerun()

        except Exception as e:
            logger.error(f"Error generating tickets: {e}")
            st.error(f"❌ Greška: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    if st.session_state.generated_tickets:
        st.markdown("---")

        if st.session_state.get('performance'):
            perf = st.session_state.performance
            st.markdown("### 📊 Istorija Performansi")

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Predviđanja", perf['n_predictions'])
            col2.metric("Prosečno Pogodaka", f"{perf['avg_best_match']:.1f}/7")
            col3.metric("Stopa 3+", f"{perf['hit_rate_3plus']:.1%}")
            col4.metric("Očekivano 3+", f"{perf.get('expected_3plus_rate', 0):.1%}")
            col5.metric("Najbolje Ikad", f"{perf['best_ever']}/7")

            vs_random = perf.get('vs_random', 1.0)
            if vs_random >= 1.0:
                st.markdown(f"""
                <div class="good-box">
                📈 Strategija: <strong>{vs_random:.2f}x</strong> bolje od nasumičnog izbora za 3+.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="math-box">
                📊 Strategija: <strong>{vs_random:.2f}x</strong> u odnosu na nasumični izbor.
                U okviru normalnog statističkog šuma.
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🎟️ Izaberite Tikete za Igranje")

        draw_date_info, is_today_info, hours_until_info = get_next_draw_info()
        st.info(format_draw_info_message(draw_date_info, is_today_info, hours_until_info))

        portfolio = st.session_state.generated_tickets
        current_strategy = st.session_state.get('current_strategy', 'coverage_optimized')

        for i, ticket in enumerate(portfolio, 1):
            col_check, col_ticket = st.columns([0.5, 9.5])
            with col_check:
                is_selected = st.checkbox(
                    f"#{i}", key=f"ticket_{i}",
                    value=i in st.session_state.selected_tickets
                )
                if is_selected and i not in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.append(i)
                elif not is_selected and i in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.remove(i)

            with col_ticket:
                numbers_html = ''.join(
                    [f'<span class="number-ball">{n:02d}</span>' for n in ticket]
                )
                label = {
                    'coverage_optimized': 'Coverage-Optimized',
                    'hybrid': 'Hibrid',
                    'pure_random': 'Nasumičan'
                }.get(current_strategy, 'Tiket')

                box_class = "ticket-box selected" if is_selected else "ticket-box"
                st.markdown(
                    f'<div class="{box_class}"><strong>Tiket {i}</strong> '
                    f'({label})<br>{numbers_html}</div>',
                    unsafe_allow_html=True
                )

        st.markdown("---")
        col_play, col_download = st.columns(2)

        n_selected = len(st.session_state.selected_tickets)

        with col_play:
            if st.button(
                f"✅ OBELEŽITE {n_selected} TIKETA KAO ODIGRANO",
                type="primary",
                disabled=n_selected == 0
            ):
                played_tracker = PlayedTicketsTracker()
                selected_nums = [
                    portfolio[i - 1] for i in st.session_state.selected_tickets
                ]
                played_tracker.save_played_tickets(
                    st.session_state.prediction_id,
                    selected_nums,
                    st.session_state.next_draw
                )
                st.success(f"✅ Obeleženo {n_selected} tiketa kao odigrano!")
                st.balloons()

        with col_download:
            if st.session_state.selected_tickets:
                selected_nums = [
                    portfolio[i - 1] for i in st.session_state.selected_tickets
                ]
                ev_info = expected_value_per_ticket()
                ticket_text = (
                    f"LOTO SRBIJA - Smart Portfolio Manager v3.0\n"
                    f"Datum Izvlačenja: {st.session_state.next_draw}\n"
                    f"Generisano: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"Strategija: {current_strategy}\n"
                    f"{'=' * 40}\n"
                    f"VAŠI IZABRANI TIKETI\n"
                    f"{'=' * 40}\n"
                )
                for idx, i in enumerate(st.session_state.selected_tickets, 1):
                    ticket = portfolio[i - 1]
                    ticket_text += f"Tiket {idx}: {' - '.join(f'{n:02d}' for n in ticket)}\n"
                ticket_text += (
                    f"\n⚠️ Igrajte odgovorno! "
                    f"EV po tiketu: {ev_info['net_ev']:.1f} RSD\n"
                    f"Srećno! 🍀"
                )
                st.download_button(
                    "💾 Preuzmite Tikete", data=ticket_text,
                    file_name=f"moji_tiketi_{st.session_state.next_draw}.txt",
                    mime="text/plain"
                )

# ============================================================================
# PAGE: WHEELING SYSTEM
# ============================================================================
elif page == "🎯 Wheeling Sistem":
    st.markdown("### 🎯 Wheeling Sistem - Matematičke Garancije")

    st.markdown("""
    <div class="good-box">
    <strong>✅ Šta je Wheeling?</strong> Izaberete grupu "ključnih" brojeva.
    Sistem generiše MINIMALAN broj tiketa koji GARANTUJU: ako se dovoljno vaših
    ključnih brojeva izvuče, bar jedan tiket ima određeni broj pogodaka.
    <br><br>
    <strong>Ovo je jedini matematički dokaziv način da poboljšate šanse!</strong>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Izaberite Ključne Brojeve")

    if 'wheel_key_numbers' not in st.session_state:
        st.session_state.wheel_key_numbers = []

    cols_per_row = 13
    selected_key_numbers = list(st.session_state.wheel_key_numbers)

    for row_start in range(MIN_NUMBER, MAX_NUMBER + 1, cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            num = row_start + j
            if num > MAX_NUMBER:
                break
            with col:
                was_selected = num in selected_key_numbers
                is_now = st.checkbox(
                    f"{num:02d}", key=f"wheel_num_{num}",
                    value=was_selected
                )
                if is_now and num not in selected_key_numbers:
                    selected_key_numbers.append(num)
                elif not is_now and num in selected_key_numbers:
                    selected_key_numbers.remove(num)

    st.session_state.wheel_key_numbers = sorted(selected_key_numbers)
    n_keys = len(selected_key_numbers)

    st.info(f"Izabrano: **{n_keys}** ključnih brojeva: "
            f"{', '.join(str(n) for n in sorted(selected_key_numbers))}")

    col_w1, col_w2 = st.columns(2)

    max_guarantee = min(7, n_keys) if n_keys >= 3 else 3

    with col_w1:
        guarantee_if_hit = st.slider(
            "Koliko vaših brojeva mora biti izvučeno",
            min_value=3, max_value=max_guarantee,
            value=3
        )

    with col_w2:
        guarantee_match = st.slider(
            "Garantovanih pogodaka na tiketu",
            min_value=3, max_value=guarantee_if_hit,
            value=3
        )

    if n_keys >= guarantee_if_hit:
        estimate = wheel_cost_estimate(n_keys, guarantee_if_hit, guarantee_match)
        st.markdown(f"""
        <div class="math-box">
        📊 <strong>Procena:</strong> Potrebno {estimate['estimated_min_tickets']} -
        {estimate['estimated_max_tickets']} tiketa za pokrivanje
        {estimate['subsets_to_cover']:,} podskupova
        </div>
        """, unsafe_allow_html=True)

    max_wheel_tickets = st.slider("Maksimalan broj tiketa", 5, 100, 30)

    can_generate = n_keys >= guarantee_if_hit

    if st.button("🎯 GENERIŠI WHEELING TIKETE", type="primary",
                 disabled=not can_generate):
        try:
            with st.spinner("Generisanje wheeling sistema..."):
                tickets, guarantee = generate_abbreviated_wheel(
                    sorted(selected_key_numbers),
                    guarantee_if_hit=guarantee_if_hit,
                    guarantee_match=guarantee_match,
                    max_tickets=max_wheel_tickets
                )

            if guarantee['verified']:
                st.success("✅ GARANCIJA VERIFIKOVANA!")
            else:
                st.warning(f"⚠️ Nepotpuna garancija - {guarantee.get('warning', '')}")

            st.markdown(f"""
            <div class="good-box">
            <strong>📜 Garancija:</strong> {guarantee['guarantee']}
            <br>Tiketa: {guarantee['n_tickets']} |
            Pokrivanje: {guarantee['coverage_pct']:.1f}%
            </div>
            """, unsafe_allow_html=True)

            for i, ticket in enumerate(tickets, 1):
                numbers_html = ''.join(
                    [f'<span class="number-ball">{n:02d}</span>' for n in ticket]
                )
                key_in = sum(1 for n in ticket if n in selected_key_numbers)
                st.markdown(
                    f'<div class="ticket-box"><strong>Tiket {i}</strong> '
                    f'({key_in} ključnih)<br>{numbers_html}</div>',
                    unsafe_allow_html=True
                )

            tracker = PredictionTracker()
            next_draw = get_next_draw_date()
            pred_id = tracker.save_prediction(
                target_draw_date=next_draw,
                strategy_name=f'wheel_{guarantee_if_hit}of{n_keys}',
                tickets=tickets,
                model_version='3.0_wheel',
                metadata=guarantee
            )
            st.caption(f"Sačuvano kao predviđanje #{pred_id}")

            ticket_text = (
                f"WHEELING SISTEM - Loto Srbija\n"
                f"Ključni brojevi: {sorted(selected_key_numbers)}\n"
                f"Garancija: {guarantee['guarantee']}\n"
                f"Verifikovano: {'DA' if guarantee['verified'] else 'NE'}\n"
                f"{'=' * 40}\n"
            )
            for i, ticket in enumerate(tickets, 1):
                ticket_text += f"Tiket {i}: {' - '.join(f'{n:02d}' for n in ticket)}\n"

            st.download_button(
                "💾 Preuzmite Wheeling Tikete",
                data=ticket_text,
                file_name=f"wheeling_{next_draw}.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error(f"Greška: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    if not can_generate and n_keys > 0:
        st.warning(f"Izaberite bar {guarantee_if_hit} ključnih brojeva "
                   f"(trenutno: {n_keys})")

# ============================================================================
# PAGE: MATHEMATICS
# ============================================================================
elif page == "📊 Matematika":
    st.markdown("### 📊 Matematika Lutrije 7/39")

    st.markdown("""
    <div class="honest-box">
    <strong>⚠️ Matematička Stvarnost:</strong> Svako izvlačenje je potpuno nezavisno.
    Prošli rezultati NE utiču na buduće. Ovo su tačne matematičke verovatnoće.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🎲 Tačne Verovatnoće")

    prob_data = []
    for matches in range(0, NUMBERS_PER_DRAW + 1):
        p = match_probability(matches)
        prize = PRIZE_TABLE.get(matches, 0)
        prob_data.append({
            'Pogodaka': f"{matches}/7",
            'Verovatnoća': f"{p:.10f}",
            'Šanse': f"1 od {int(1/p):,}" if p > 0 else "-",
            'Nagrada (RSD)': f"{prize:,}" if prize > 0 else "-",
            'Doprinos EV': f"{p * prize:.2f} RSD" if prize > 0 else "-"
        })

    st.table(prob_data)

    ev_data = expected_value_per_ticket()
    col_ev1, col_ev2, col_ev3 = st.columns(3)
    col_ev1.metric("Cena Tiketa", f"{TICKET_COST} RSD")
    col_ev2.metric("Očekivani Povraćaj", f"{ev_data['expected_value']:.2f} RSD")
    col_ev3.metric("ROI", f"{ev_data['roi_percent']:.1f}%")

    st.markdown(f"""
    <div class="math-box">
    💰 <strong>Šta ovo znači:</strong> Za svaki tiket od {TICKET_COST} RSD,
    matematički očekujete povraćaj od {ev_data['expected_value']:.2f} RSD.
    To je gubitak od {abs(ev_data['net_ev']):.2f} RSD po tiketu u proseku.
    <br><br>
    Ukupan broj kombinacija: <strong>{TOTAL_COMBINATIONS:,}</strong>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📦 Kalkulator Portfolija")
    n_calc = st.slider("Broj tiketa za kalkulaciju", 1, 50, 10, key="calc_tickets")
    pev = portfolio_expected_value(n_calc)

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("Ukupna Cena", f"{pev['total_cost']:,} RSD")
    col_p2.metric("Šansa za 3+", f"{pev['prob_any_3plus']:.2%}")
    col_p3.metric("Šansa za 4+", f"{pev['prob_any_4plus']:.4%}")
    col_p4.metric("Šansa za 5+", f"{pev['prob_any_5plus']:.6%}")

    st.markdown("#### 🏦 Bankroll Upravljanje")
    bankroll = st.number_input("Vaš budžet (RSD)", min_value=1000,
                                max_value=1000000, value=10000, step=1000)
    kelly = kelly_criterion_lottery(bankroll)

    st.markdown(f"""
    <div class="math-box">
    📊 <strong>Kelly Criterion kaže:</strong> {kelly['kelly_says']}
    <br><br>
    🎯 <strong>Preporuka:</strong> {kelly['recommendation']}
    <br><br>
    💰 Maksimalan odgovoran ulog: <strong>{kelly['entertainment_budget']:.0f} RSD</strong>
    ({kelly['max_responsible_tickets']} tiketa)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📈 Statistika Brojeva (Opisna)")
    st.caption("⚠️ Ovo su OPISNE statistike. Ne predviđaju buduća izvlačenja.")

    try:
        summary = get_number_summary(n_recent=20)
        if summary:
            stats_list = []
            for num in sorted(summary.keys()):
                data = summary[num]
                stats_list.append({
                    'Broj': num,
                    'Ukupno': data['total_appearances'],
                    'Frekvencija': f"{data['overall_frequency']:.3f}",
                    'Očekivano': f"{data['expected_frequency']:.3f}",
                    'Odstupanje': f"{data['deviation']:+.3f}",
                    'Razmak': data['current_gap'],
                    'Status': data['status']
                })
            df_stats = pd.DataFrame(stats_list)
            st.dataframe(df_stats, hide_index=True)
    except Exception as e:
        st.warning(f"Nema dovoljno podataka: {e}")

# ============================================================================
# PAGE: FAIRNESS TEST
# ============================================================================
elif page == "🔬 Fer Igra Test":
    st.markdown("### 🔬 Statistički Test Fer Igre")

    st.markdown("""
    <div class="good-box">
    <strong>✅ Zašto je ovo važno:</strong> Ovo testira da li lutrija zaista jeste
    nasumična. Ako svi testovi prođu, to DOKAZUJE da nijedan metod
    predikcije ne može raditi.
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔬 POKRENI TESTOVE", type="primary"):
        with st.spinner("Pokrećem statističke testove..."):
            try:
                df = load_draws()

                if len(df) < 30:
                    st.warning(f"Potrebno minimum 30 izvlačenja. Trenutno: {len(df)}")
                else:
                    results = test_lottery_fairness(df)

                    if results['overall']['is_fair']:
                        st.success(f"✅ {results['overall']['conclusion']}")
                    else:
                        st.warning(f"⚠️ {results['overall']['conclusion']}")

                    st.info(f"Analizirano: {results['n_draws']} izvlačenja")

                    st.markdown("#### 1️⃣ Hi-Kvadrat Test Uniformnosti")
                    chi = results['chi_square']
                    st.write(f"- **Statistika:** {chi['statistic']:.2f}")
                    st.write(f"- **p-vrednost:** {chi['p_value']:.4f}")
                    st.write(f"- **Zaključak:** {chi['conclusion']}")

                    st.markdown("#### 2️⃣ Runs Test Nasumičnosti")
                    runs = results['runs_test']
                    st.write(f"- **Testirano:** {runs['n_numbers_tested']} brojeva")
                    st.write(f"- **Nenasumičnih:** {runs['n_non_random']}")
                    st.write(f"- **Zaključak:** {runs['conclusion']}")

                    st.markdown("#### 3️⃣ Test Serijske Korelacije")
                    serial = results['serial_correlation']
                    st.write(f"- **Korelacija:** {serial['correlation']:.4f}")
                    st.write(f"- **Zaključak:** {serial['conclusion']}")

                    st.markdown("#### 4️⃣ Test Frekvencije Parova")
                    pair = results.get('pair_test', {})
                    st.write(f"- **Zaključak:** {pair.get('conclusion', 'N/A')}")

                    st.markdown("---")
                    overall = results['overall']
                    box_class = 'good-box' if overall['is_fair'] else 'honest-box'
                    st.markdown(f"""
                    <div class="{box_class}">
                    <strong>{overall['conclusion']}</strong>
                    <br>Testovi: {overall['tests_passed']}/{overall['tests_total']}
                    <br><strong>Preporuka:</strong> {overall['recommendation']}
                    </div>
                    """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Greška: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

# ============================================================================
# PAGE: HISTORY
# ============================================================================
elif page == "📈 Istorija":
    st.markdown("### 📈 Istorija Predviđanja")

    tracker = PredictionTracker()
    evaluated = tracker.auto_evaluate_pending()
    if evaluated > 0:
        st.info(f"Automatski evaluirano {evaluated} predviđanja")

    for strat in ['coverage_optimized', 'hybrid', 'pure_random']:
        perf = tracker.get_strategy_performance(strat, window=50)
        if perf and perf['n_predictions'] > 0:
            st.markdown(f"#### Strategija: `{strat}`")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Predviđanja", perf['n_predictions'])
            c2.metric("Prosečno", f"{perf['avg_best_match']:.2f}/7")
            c3.metric("Stopa 3+", f"{perf['hit_rate_3plus']:.1%}")
            c4.metric("vs Nasumično", f"{perf.get('vs_random', 1.0):.2f}x")
            c5.metric("Ukupna Dobit", f"{perf['total_prize_won']:,.0f} RSD")

    st.markdown("#### Poslednja Predviđanja")
    session = get_session()
    try:
        recent = session.query(Prediction).order_by(
            Prediction.created_at.desc()
        ).limit(20).all()

        for pred in recent:
            result_str = "⏳ Čeka evaluaciju"
            if pred.evaluated:
                result = session.query(PredictionResult).filter_by(
                    prediction_id=pred.prediction_id
                ).first()
                if result:
                    icon = '🎉' if result.best_match >= 3 else '📊'
                    result_str = (f"{icon} Najbolje: {result.best_match}/7 | "
                                  f"Nagrada: {result.prize_value:,.0f} RSD")

            with st.expander(
                f"#{pred.prediction_id} | {pred.target_draw_date} | "
                f"{pred.strategy_name} | {result_str}"
            ):
                tickets = json.loads(pred.tickets)
                for i, ticket in enumerate(tickets, 1):
                    st.write(f"Tiket {i}: {ticket}")

                if pred.evaluated:
                    result = session.query(PredictionResult).filter_by(
                        prediction_id=pred.prediction_id
                    ).first()
                    if result:
                        actual = json.loads(result.actual_numbers)
                        st.write(f"**Izvučeni:** {actual}")
                        matches = json.loads(result.ticket_matches)
                        st.write(f"**Pogoci po tiketu:** {matches}")
    finally:
        session.close()

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""
<div class="math-box">
💡 <strong>Savet:</strong> Koristite Coverage Optimizaciju za maksimalno pokrivanje
ili Wheeling Sistem za matematičke garancije. Igrajte odgovorno - lutrija je zabava,
ne investicija.
<br><br>
📊 Ukupan broj kombinacija u Loto 7/39: <strong>{TOTAL_COMBINATIONS:,}</strong>
</div>
""", unsafe_allow_html=True)