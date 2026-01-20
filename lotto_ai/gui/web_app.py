"""
Streamlit Web App for Lotto Max AI
Simple one-button interface for non-technical users
"""
import streamlit as st
import sys
from pathlib import Path
import hashlib

# Add parent directories to path
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from lotto_ai.scraper.scrape_lotto_max import main as scrape_data
from lotto_ai.features.features import build_feature_matrix
from lotto_ai.tracking.prediction_tracker import PredictionTracker
from lotto_ai.learning.adaptive_learner import AdaptiveLearner
from lotto_ai.models.production_model import (
    generate_adaptive_portfolio,
    portfolio_statistics
)
from datetime import datetime, timedelta

def get_next_draw_date():
    """Calculate next draw date"""
    today = datetime.now()
    days_ahead = 0
    while True:
        days_ahead += 1
        next_date = today + timedelta(days=days_ahead)
        if next_date.weekday() in [1, 4]:
            return next_date.strftime('%Y-%m-%d')

# ============================================
# PASSWORD PROTECTION
# ============================================
def check_password():
    """Returns `True` if user entered correct password"""
    
    def password_entered():
        """Checks whether password is correct"""
        # Hash the password for security
        entered_password = st.session_state["password"]
        correct_password = "gotovac71"  # ⚠️ CHANGE THIS!
        
        # Simple hash comparison
        if entered_password == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # First run or password not correct
    if "password_correct" not in st.session_state:
        # Show password input
        st.text_input(
            "🔐 Enter Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.info("Please enter the password to access the app")
        return False
    
    # Password incorrect
    elif not st.session_state["password_correct"]:
        st.text_input(
            "🔐 Enter Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("😕 Password incorrect")
        return False
    
    # Password correct
    else:
        return True

# Check password before showing app
if not check_password():
    st.stop()  # Don't continue if not authenticated

# ============================================
# PLAYED TICKETS TRACKING
# ============================================
class PlayedTicketsTracker:
    """Track which tickets user actually played"""
    
    def __init__(self, db_path):
        from lotto_ai.config import DB_PATH
        self.db_path = DB_PATH
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS played_tickets (
            play_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            ticket_numbers TEXT NOT NULL,
            played_at TEXT NOT NULL,
            draw_date TEXT NOT NULL,
            FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
        )
        """)
        conn.commit()
        conn.close()
    
    def save_played_tickets(self, prediction_id, tickets, draw_date):
        """Save which tickets were actually played"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        for ticket in tickets:
            cur.execute("""
            INSERT INTO played_tickets (prediction_id, ticket_numbers, played_at, draw_date)
            VALUES (?, ?, ?, ?)
            """, (
                prediction_id,
                json.dumps(ticket),
                datetime.now().isoformat(),
                draw_date
            ))
        
        conn.commit()
        conn.close()
    
    def get_played_tickets(self, draw_date):
        """Get tickets that were played for a specific draw"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        SELECT ticket_numbers FROM played_tickets
        WHERE draw_date = ?
        """, (draw_date,))
        
        tickets = [json.loads(row[0]) for row in cur.fetchall()]
        conn.close()
        return tickets

# ============================================
# PAGE CONFIG
# ============================================
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

# Sidebar
with st.sidebar:
    st.markdown("### ℹ️ How It Works")
    st.info("""
    **Simple Process:**
    
    1️⃣ Click **Generate Numbers**
    
    2️⃣ Choose 3-4 tickets to play
    
    3️⃣ Click **Mark as Played**
    
    4️⃣ Come back after draw
    
    🧠 **AI learns from played tickets!**
    """)
    
    st.markdown("---")
    
    # Number of tickets selector
    st.markdown("### ⚙️ Settings")
    n_tickets = st.slider(
        "Number of tickets to generate",
        min_value=3,
        max_value=10,
        value=4,
        help="Choose how many tickets to generate"
    )
    
    # Logout button
    st.markdown("---")
    if st.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

# Initialize session state
if 'generated_tickets' not in st.session_state:
    st.session_state.generated_tickets = None
if 'selected_tickets' not in st.session_state:
    st.session_state.selected_tickets = []
if 'prediction_id' not in st.session_state:
    st.session_state.prediction_id = None
if 'next_draw' not in st.session_state:
    st.session_state.next_draw = None

# Main content
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Generate Button
    if st.button("🎲 GENERATE NUMBERS", 
                 use_container_width=True, 
                 type="primary"):
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Scrape
            status_text.text("📥 Checking for new draw results...")
            progress_bar.progress(10)
            scrape_data()
            
            # Step 2: Evaluate
            status_text.text("🔍 Evaluating previous predictions...")
            progress_bar.progress(25)
            tracker = PredictionTracker()
            tracker.auto_evaluate_pending()
            
            # Step 3: Learn
            status_text.text("🧠 Learning from results...")
            progress_bar.progress(40)
            learner = AdaptiveLearner()
            learner.update_weights(strategy_name='hybrid_v1', window=20)
            
            perf = tracker.get_strategy_performance('hybrid_v1', window=50)
            
            # Step 4: Build features
            status_text.text("⚙️ Analyzing historical data...")
            progress_bar.progress(60)
            features = build_feature_matrix()
            
            # Step 5: Generate (use selected number)
            status_text.text("🎲 Generating your lucky numbers...")
            progress_bar.progress(80)
            portfolio, weights = generate_adaptive_portfolio(
                features, 
                n_tickets=n_tickets, 
                use_adaptive=True
            )
            
            # Save prediction
            next_draw = get_next_draw_date()
            prediction_id = tracker.save_prediction(
                target_draw_date=next_draw,
                strategy_name='hybrid_v1',
                tickets=portfolio,
                model_version='2.0_adaptive',
                metadata=weights
            )
            
            # Store in session state
            st.session_state.generated_tickets = portfolio
            st.session_state.prediction_id = prediction_id
            st.session_state.next_draw = next_draw
            st.session_state.selected_tickets = []
            st.session_state.weights = weights
            st.session_state.performance = perf
            
            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()
            
            st.success(f"✅ Generated {len(portfolio)} tickets for draw on **{next_draw}**")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

# Display generated tickets with selection
if st.session_state.generated_tickets:
    st.markdown("---")
    
    # Performance metrics
    if st.session_state.get('performance'):
        perf = st.session_state.performance
        
        st.markdown("### 📊 AI Performance")
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            st.metric("Predictions", perf['n_predictions'])
        with metric_col2:
            st.metric("Avg Match", f"{perf['avg_best_match']:.1f}/7")
        with metric_col3:
            st.metric("Hit Rate (3+)", f"{perf['hit_rate_3plus']:.1%}")
        with metric_col4:
            st.metric("Best Ever", f"{perf['best_ever']}/7")
    
    st.markdown("---")
    st.markdown("### 🎟️ Select Tickets to Play")
    st.caption(f"Choose 3-4 tickets for draw on **{st.session_state.next_draw}**")
    
    # Display tickets with checkboxes
    portfolio = st.session_state.generated_tickets
    weights = st.session_state.weights
    n_freq = weights['n_freq_tickets']
    
    # AI-Optimized tickets
    st.markdown("#### 📊 AI-Optimized Tickets")
    
    for i, ticket in enumerate(portfolio[:n_freq], 1):
        col_check, col_ticket = st.columns([0.5, 9.5])
        
        with col_check:
            selected = st.checkbox(
                f"#{i}",
                key=f"ticket_{i}",
                value=i in st.session_state.selected_tickets
            )
            if selected and i not in st.session_state.selected_tickets:
                st.session_state.selected_tickets.append(i)
            elif not selected and i in st.session_state.selected_tickets:
                st.session_state.selected_tickets.remove(i)
        
        with col_ticket:
            numbers_html = ''.join([
                f'<span class="number-ball">{n:02d}</span>' 
                for n in ticket
            ])
            box_class = "ticket-box selected" if selected else "ticket-box"
            st.markdown(f"""
            <div class="{box_class}">
                <strong>Ticket {i}</strong> (AI-Optimized)<br>
                {numbers_html}
            </div>
            """, unsafe_allow_html=True)
    
    # Random tickets
    if n_freq < len(portfolio):
        st.markdown("#### 🎲 Random Mix Tickets")
        
        for i, ticket in enumerate(portfolio[n_freq:], n_freq + 1):
            col_check, col_ticket = st.columns([0.5, 9.5])
            
            with col_check:
                selected = st.checkbox(
                    f"#{i}",
                    key=f"ticket_{i}",
                    value=i in st.session_state.selected_tickets
                )
                if selected and i not in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.append(i)
                elif not selected and i in st.session_state.selected_tickets:
                    st.session_state.selected_tickets.remove(i)
            
            with col_ticket:
                numbers_html = ''.join([
                    f'<span class="number-ball">{n:02d}</span>' 
                    for n in ticket
                ])
                box_class = "ticket-box selected" if selected else "ticket-box"
                st.markdown(f"""
                <div class="{box_class}">
                    <strong>Ticket {i}</strong> (Random Mix)<br>
                    {numbers_html}
                </div>
                """, unsafe_allow_html=True)
    
    # Mark as Played button
    st.markdown("---")
    
    col_play, col_download = st.columns(2)
    
    with col_play:
        if st.button(
            f"✅ MARK {len(st.session_state.selected_tickets)} TICKETS AS PLAYED",
            use_container_width=True,
            type="primary",
            disabled=len(st.session_state.selected_tickets) == 0
        ):
            # Save played tickets
            played_tracker = PlayedTicketsTracker(None)
            selected_ticket_numbers = [
                portfolio[i-1] for i in st.session_state.selected_tickets
            ]
            
            played_tracker.save_played_tickets(
                st.session_state.prediction_id,
                selected_ticket_numbers,
                st.session_state.next_draw
            )
            
            st.success(f"✅ Marked {len(st.session_state.selected_tickets)} tickets as played for {st.session_state.next_draw}!")
            st.balloons()
    
    with col_download:
        # Download selected tickets
        if st.session_state.selected_tickets:
            selected_ticket_numbers = [
                portfolio[i-1] for i in st.session_state.selected_tickets
            ]
            
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
            
            st.download_button(
                label="💾 Download Selected Tickets",
                data=ticket_text,
                file_name=f"my_tickets_{st.session_state.next_draw}.txt",
                mime="text/plain",
                use_container_width=True
            )

# Footer
st.markdown("---")
st.info("💡 **Tip:** Select 3-4 tickets, mark them as played, then come back after the draw for the AI to learn!")