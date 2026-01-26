"""
Streamlit UI - CLOUD SAFE VERSION
No scraping, only reads from database
"""
import streamlit as st
import sys
from pathlib import Path
import json

# Add parent to path
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from lotto_ai.core.db import init_db, get_session, Draw
from lotto_ai.core.tracker import PredictionTracker, PlayedTicketsTracker
from lotto_ai.learning.adaptive_learner import AdaptiveLearner
from lotto_ai.models.production_model import generate_adaptive_portfolio, portfolio_statistics
from lotto_ai.features.features import build_feature_matrix
from lotto_ai.config import SCRAPING_ENABLED, IS_CLOUD, logger
from datetime import datetime, timedelta

# Initialize DB
init_db()

def get_next_draw_info():
    """Calculate next draw date"""
    now = datetime.now()
    current_hour = now.hour
    current_weekday = now.weekday()
    
    DRAW_HOUR = 21
    DRAW_DAYS = [1, 4]
    
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
            return f"🎯 **TODAY'S DRAW** - {draw_date} at 9:00 PM (in ~{int(hours_until)}h)"
        else:
            return f"⚡ **TODAY'S DRAW** - {draw_date} - HAPPENING SOON!"
    else:
        days_until = int(hours_until / 24)
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_name = draw_dt.strftime('%A')
        return f"📅 Next draw: **{day_name}, {draw_date}** (in {days_until} day{'s' if days_until != 1 else ''})"

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
        st.markdown("### 🔐 Lotto Max AI - Login")
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.info("💡 Enter password to access")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password")
        return False
    else:
        return True

if not check_password():
    st.stop()

# Page config
st.set_page_config(
    page_title="Lotto Max AI",
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
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .ticket-box {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
    }
    .ticket-box.selected {
        background: #e3f2fd;
        border-left: 5px solid #2196F3;
    }
    .number-ball {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    <h1>🎰 Lotto Max AI</h1>
    <p style="font-size: 1.2rem; margin: 0;">Smart Number Generator with Learning AI</p>
</div>
""", unsafe_allow_html=True)

# Cloud warning
if IS_CLOUD:
    st.warning("⚠️ Running in cloud mode - automatic scraping is disabled. Database is read-only.")

# Sidebar
with st.sidebar:
    st.markdown("### ℹ️ How It Works")
    st.info("""
    1️⃣ Click **Generate Numbers**
    2️⃣ Choose 3-4 tickets
    3️⃣ Click **Mark as Played**
    4️⃣ Come back after draw
    🧠 **AI learns from played tickets!**
    """)
    
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    n_tickets = st.slider("Number of tickets", 3, 10, 4)
    
    st.markdown("---")
    st.markdown("### ⏰ Next Draw")
    draw_date, is_today, hours_until = get_next_draw_info()
    
    if is_today:
        st.success(f"**TODAY** at 9:00 PM")
        progress = min((9 - hours_until) / 9, 1.0)
        st.progress(progress)
        st.caption(f"~{int(hours_until)} hours remaining")
    else:
        days_until = int(hours_until / 24)
        draw_dt = datetime.strptime(draw_date, '%Y-%m-%d')
        day_name = draw_dt.strftime('%A')
        st.info(f"**{day_name}**\n{draw_date}")
        st.caption(f"In {days_until} day{'s' if days_until != 1 else ''}")
    
    st.markdown("---")
    if st.button("🚪 Logout"):
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
    if st.button("🎲 GENERATE NUMBERS", use_container_width=True, type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Evaluate
            status_text.text("🔍 Evaluating previous predictions...")
            progress_bar.progress(25)
            tracker = PredictionTracker()
            tracker.auto_evaluate_pending()
            
            # Learn
            status_text.text("🧠 Learning from results...")
            progress_bar.progress(40)
            learner = AdaptiveLearner()
            learner.update_weights(strategy_name='hybrid_v1', window=20)
            
            perf = tracker.get_strategy_performance('hybrid_v1', window=50)
            
            # Features
            status_text.text("⚙️ Analyzing data...")
            progress_bar.progress(60)
            features = build_feature_matrix()
            
            # Generate
            status_text.text("🎲 Generating numbers...")
            progress_bar.progress(80)
            portfolio, weights = generate_adaptive_portfolio(features, n_tickets=n_tickets, use_adaptive=True)
            
            # Save
            next_draw = get_next_draw_date()
            prediction_id = tracker.save_prediction(
                target_draw_date=next_draw,
                strategy_name='hybrid_v1',
                tickets=portfolio,
                model_version='2.0_adaptive',
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
            
            st.success(f"✅ Generated {len(portfolio)} tickets!")
            st.info(draw_message)
            st.rerun()
            
        except Exception as e:
            logger.error(f"Error generating tickets: {e}")
            st.error(f"❌ Error: {str(e)}")

# Display tickets (same as before - keeping your existing ticket display code)
if st.session_state.generated_tickets:
    st.markdown("---")
    
    if st.session_state.get('performance'):
        perf = st.session_state.performance
        st.markdown("### 📊 AI Performance")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Predictions", perf['n_predictions'])
        col2.metric("Avg Match", f"{perf['avg_best_match']:.1f}/7")
        col3.metric("Hit Rate (3+)", f"{perf['hit_rate_3plus']:.1%}")
        col4.metric("Best Ever", f"{perf['best_ever']}/7")
    
    st.markdown("---")
    st.markdown("### 🎟️ Select Tickets to Play")
    
    draw_date, is_today, hours_until = get_next_draw_info()
    draw_message = format_draw_info_message(draw_date, is_today, hours_until)
    st.info(draw_message)
    
    portfolio = st.session_state.generated_tickets
    weights = st.session_state.weights
    n_freq = weights['n_freq_tickets']
    
    st.markdown("#### 📊 AI-Optimized Tickets")
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
            st.markdown(f'<div class="{box_class}"><strong>Ticket {i}</strong> (AI-Optimized)<br>{numbers_html}</div>', unsafe_allow_html=True)
    
    if n_freq < len(portfolio):
        st.markdown("#### 🎲 Random Mix Tickets")
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
                st.markdown(f'<div class="{box_class}"><strong>Ticket {i}</strong> (Random)<br>{numbers_html}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    col_play, col_download = st.columns(2)
    
    with col_play:
        if st.button(f"✅ MARK {len(st.session_state.selected_tickets)} TICKETS AS PLAYED", 
                     use_container_width=True, type="primary", 
                     disabled=len(st.session_state.selected_tickets) == 0):
            played_tracker = PlayedTicketsTracker()
            selected_ticket_numbers = [portfolio[i-1] for i in st.session_state.selected_tickets]
            played_tracker.save_played_tickets(st.session_state.prediction_id, selected_ticket_numbers, st.session_state.next_draw)
            st.success(f"✅ Marked {len(st.session_state.selected_tickets)} tickets as played!")
            st.balloons()
    
    with col_download:
        if st.session_state.selected_tickets:
            selected_ticket_numbers = [portfolio[i-1] for i in st.session_state.selected_tickets]
            ticket_text = f"""LOTTO MAX - Selected Tickets
Draw Date: {st.session_state.next_draw}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*40}
YOUR SELECTED TICKETS
{'='*40}

"""
            for idx, i in enumerate(st.session_state.selected_tickets, 1):
                ticket = portfolio[i-1]
                ticket_text += f"Ticket {idx}: {' - '.join(f'{n:02d}' for n in ticket)}\n"
            ticket_text += f"\nGood luck! 🍀"
            
            st.download_button("💾 Download Selected Tickets", data=ticket_text, 
                             file_name=f"my_tickets_{st.session_state.next_draw}.txt", 
                             mime="text/plain", use_container_width=True)

st.markdown("---")
st.info("💡 **Tip:** Select 3-4 tickets, mark them as played, then come back after the draw!")