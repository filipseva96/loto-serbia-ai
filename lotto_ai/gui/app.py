"""
Streamlit UI for Loto Serbia
"""
import streamlit as st
import sys
from pathlib import Path
import json

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from lotto_ai.core.db import init_db, get_session, Draw
from lotto_ai.core.tracker import PredictionTracker, PlayedTicketsTracker
from lotto_ai.learning.adaptive_learner import AdaptiveLearner
from lotto_ai.models.production_model import generate_adaptive_portfolio, portfolio_statistics
from lotto_ai.features.features import build_feature_matrix
from lotto_ai.config import SCRAPING_ENABLED, IS_CLOUD, logger, DRAW_DAYS, DRAW_HOUR
from datetime import datetime, timedelta

init_db()

def get_next_draw_info():
    """Calculate next draw date (Tue/Thu/Fri for Serbia)"""
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
    if is_today:
        if hours_until > 2:
            return f"🎯 **DANAŠNJE IZVLAČENJE** - {draw_date} u 21:00 (za ~{int(hours_until)}h)"
        else:
            return f"⚡ **DANAŠNJE IZVLAČENJE** - {draw_date} - USKORO!"
    else:
        days_until = int(hours_until / 24)
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_name = draw_dt.strftime('%A')
        return f"📅 Sledeće izvlačenje: **{day_name}, {draw_date}** (za {days_until} dan{'a' if days_until != 1 else ''})"

def check_password():
    """Password protection"""
    def password_entered():
        try:
            correct_password = st.secrets.get("app_password", "gotovac71")
        except:
            correct_password = "gotovac71"
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.markdown("### 🔐 Loto Srbija AI - Prijava")
        st.text_input("Unesite lozinku", type="password", on_change=password_entered, key="password")
        st.info("💡 Unesite lozinku za pristup")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Unesite lozinku", type="password", on_change=password_entered, key="password")
        st.error("❌ Pogrešna lozinka")
        return False
    else:
        return True

if not check_password():
    st.stop()

# Page config
st.set_page_config(
    page_title="Loto Srbija AI",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>🎰 Loto Srbija AI</h1>
    <p style="font-size: 1.2rem; margin: 0;">Pametni Generator Brojeva sa AI Učenjem</p>
    <p style="font-size: 0.9rem; margin: 0; opacity: 0.9;">LOTO 7/39</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ℹ️ Kako Radi")
    st.info("""
    1️⃣ Kliknite **Generiši Brojeve**
    2️⃣ Izaberite 3-4 tiketa
    3️⃣ Kliknite **Obeležite kao Odigrano**
    4️⃣ Vratite se posle izvlačenja
    🧠 **AI uči iz odigranih tiketa!**
    """)
    
    st.markdown("---")
    st.markdown("### ⚙️ Podešavanja")
    n_tickets = st.slider("Broj tiketa", 3, 10, 4)
    
    st.markdown("---")
    st.markdown("### ⏰ Sledeće Izvlačenje")
    draw_date, is_today, hours_until = get_next_draw_info()
    
    if is_today:
        st.success(f"**DANAS** u 21:00")
        progress = min((9 - hours_until) / 9, 1.0)
        st.progress(progress)
        st.caption(f"~{int(hours_until)} sati preostalo")
    else:
        days_until = int(hours_until / 24)
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_name = draw_dt.strftime('%A')
        st.info(f"**{day_name}**\n{draw_date}")
        st.caption(f"Za {days_until} dan{'a' if days_until != 1 else ''}")
    
    st.markdown("---")
    if st.button("🚪 Odjava"):
        st.session_state["password_correct"] = False
        st.rerun()

# Initialize session state
if 'generated_tickets' not in st.session_state:
    st.session_state.generated_tickets = None
if 'selected_tickets' not in st.session_state:
    st.session_state.selected_tickets = []

# Main content
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("🎲 GENERIŠI BROJEVE", use_container_width=True, type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("🔍 Evaluacija prethodnih predviđanja...")
            progress_bar.progress(25)
            tracker = PredictionTracker()
            tracker.auto_evaluate_pending()
            
            status_text.text("🧠 Učenje iz rezultata...")
            progress_bar.progress(40)
            learner = AdaptiveLearner()
            learner.update_weights(strategy_name='hybrid_v1', window=20)
            
            perf = tracker.get_strategy_performance('hybrid_v1', window=50)
            
            status_text.text("⚙️ Analiza podataka...")
            progress_bar.progress(60)
            features = build_feature_matrix()
            
            status_text.text("🎲 Generisanje brojeva...")
            progress_bar.progress(80)
            portfolio, weights = generate_adaptive_portfolio(features, n_tickets=n_tickets, use_adaptive=True)
            
            next_draw = get_next_draw_date()
            prediction_id = tracker.save_prediction(
                target_draw_date=next_draw,
                strategy_name='hybrid_v1',
                tickets=portfolio,
                model_version='2.0_adaptive_serbia',
                metadata=weights
            )
            
            st.session_state.generated_tickets = portfolio
            st.session_state.prediction_id = prediction_id
            st.session_state.next_draw = next_draw
            st.session_state.selected_tickets = []
            st.session_state.weights = weights
            st.session_state.performance = perf
            
            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()
            
            draw_date, is_today, hours_until = get_next_draw_info()
            draw_message = format_draw_info_message(draw_date, is_today, hours_until)
            
            st.success(f"✅ Generisano {len(portfolio)} tiketa!")
            st.info(draw_message)
            st.rerun()
            
        except Exception as e:
            logger.error(f"Error generating tickets: {e}")
            st.error(f"❌ Greška: {str(e)}")

# Display tickets
if st.session_state.generated_tickets:
    st.markdown("---")
    
    if st.session_state.get('performance'):
        perf = st.session_state.performance
        st.markdown("### 📊 AI Performanse")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Predviđanja", perf['n_predictions'])
        col2.metric("Prosečno Pogodaka", f"{perf['avg_best_match']:.1f}/7")
        col3.metric("Stopa Pogotka (3+)", f"{perf['hit_rate_3plus']:.1%}")
        col4.metric("Najbolje Ikad", f"{perf['best_ever']}/7")
    
    st.markdown("---")
    st.markdown("### 🎟️ Izaberite Tikete za Igranje")
    
    draw_date, is_today, hours_until = get_next_draw_info()
    draw_message = format_draw_info_message(draw_date, is_today, hours_until)
    st.info(draw_message)
    
    portfolio = st.session_state.generated_tickets
    weights = st.session_state.weights
    n_freq = weights['n_freq_tickets']
    
    st.markdown("#### 📊 AI-Optimizovani Tiketi")
    for i, ticket in enumerate(portfolio[:n_freq], 1):
        col_check, col_ticket = st.columns([0.5, 9.5])
        with col_check:
            selected = st.checkbox(f"#{i}", key=f"ticket_{i}", value=i in st.session_state.selected_tickets)
            if selected and i not in st.session_state.selected_tickets:
                st.session_state.selected_tickets.append(i)
            elif not selected and i in st.session_state.selected_tickets:
                st.session_state.selected_tickets.remove(i)
        
        with col_ticket:
            numbers_html = ''.join([f'<span class="number-ball">{n:02d}</span>' for n in ticket])
            box_class = "ticket-box selected" if selected else "ticket-box"
            st.markdown(f'<div class="{box_class}"><strong>Tiket {i}</strong> (AI-Optimizovan)<br>{numbers_html}</div>', unsafe_allow_html=True)
    
    if n_freq < len(portfolio):
        st.markdown("#### 🎲 Nasumični Tiketi")
        for i, ticket in enumerate(portfolio[n_freq:], n_freq + 1):
            col_check, col_ticket = st.columns([0.5, 9.5])
            with col_check:
                selected = st.checkbox(f"#{i}", key=f"ticket_{i}", value=i in st.session_state.selected_tickets)
                if selected and i not in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.append(i)
                elif not selected and i in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.remove(i)
            
            with col_ticket:
                numbers_html = ''.join([f'<span class="number-ball">{n:02d}</span>' for n in ticket])
                box_class = "ticket-box selected" if selected else "ticket-box"
                st.markdown(f'<div class="{box_class}"><strong>Tiket {i}</strong> (Nasumičan)<br>{numbers_html}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    col_play, col_download = st.columns(2)
    
    with col_play:
        if st.button(f"✅ OBELEŽITE {len(st.session_state.selected_tickets)} TIKETA KAO ODIGRANO", 
                     use_container_width=True, type="primary", 
                     disabled=len(st.session_state.selected_tickets) == 0):
            played_tracker = PlayedTicketsTracker()
            selected_ticket_numbers = [portfolio[i-1] for i in st.session_state.selected_tickets]
            played_tracker.save_played_tickets(st.session_state.prediction_id, selected_ticket_numbers, st.session_state.next_draw)
            st.success(f"✅ Obeleženo {len(st.session_state.selected_tickets)} tiketa kao odigrano!")
            st.balloons()
    
    with col_download:
        if st.session_state.selected_tickets:
            selected_ticket_numbers = [portfolio[i-1] for i in st.session_state.selected_tickets]
            ticket_text = f"""LOTO SRBIJA - Izabrani Tiketi
Datum Izvlačenja: {st.session_state.next_draw}
Generisano: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*40}
VAŠI IZABRANI TIKETI
{'='*40}
"""
            for idx, i in enumerate(st.session_state.selected_tickets, 1):
                ticket = portfolio[i-1]
                ticket_text += f"Tiket {idx}: {' - '.join(f'{n:02d}' for n in ticket)}\n"
            ticket_text += f"\nSrećno! 🍀"
            
            st.download_button("💾 Preuzmite Izabrane Tikete", data=ticket_text, 
                             file_name=f"moji_tiketi_{st.session_state.next_draw}.txt", 
                             mime="text/plain", use_container_width=True)

st.markdown("---")
st.info("💡 **Savet:** Izaberite 3-4 tiketa, obeležite ih kao odigrane, zatim se vratite posle izvlačenja!")