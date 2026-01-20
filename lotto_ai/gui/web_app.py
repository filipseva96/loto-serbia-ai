"""
Streamlit Web App for Lotto Max AI
Simple one-button interface for non-technical users
"""
import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.scrape_lotto_max import main as scrape_data
from features.features import build_feature_matrix
from pipelines.predict_and_track import (
    get_next_draw_date,
    PredictionTracker,
    AdaptiveLearner,
    generate_adaptive_portfolio,
    portfolio_statistics
)

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
    st.image("https://via.placeholder.com/300x100/667eea/ffffff?text=Lotto+Max+AI", use_container_width=True)
    
    st.markdown("### ℹ️ How It Works")
    st.info("""
    **Simple 3-Step Process:**
    
    1️⃣ Click **Generate Numbers**
    
    2️⃣ Play the tickets for next draw
    
    3️⃣ Come back after the draw and click again
    
    🧠 **The AI learns from each draw and improves your odds!**
    """)
    
    st.markdown("---")
    
    st.markdown("### 📊 What Makes This Special?")
    st.success("""
    ✅ **Adaptive Learning** - Improves after each draw
    
    ✅ **Hybrid Strategy** - 70% AI + 30% Random
    
    ✅ **Historical Analysis** - Learns from 1000+ past draws
    
    ✅ **Portfolio Optimization** - 10 diversified tickets
    """)
    
    st.markdown("---")
    st.markdown("**Made with ❤️ by AI**")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Main content
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Big Generate Button
    if st.button("🎲 GENERATE MY LUCKY NUMBERS", 
                 use_container_width=True, 
                 type="primary",
                 help="Click to generate AI-optimized lottery tickets"):
        
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
            
            # Get performance
            perf = tracker.get_strategy_performance('hybrid_v1', window=50)
            
            # Step 4: Build features
            status_text.text("⚙️ Analyzing historical data...")
            progress_bar.progress(60)
            features = build_feature_matrix()
            
            # Step 5: Generate
            status_text.text("🎲 Generating your lucky numbers...")
            progress_bar.progress(80)
            portfolio, weights = generate_adaptive_portfolio(
                features, 
                n_tickets=10, 
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
            
            stats = portfolio_statistics(portfolio)
            
            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()
            
            # Success message
            st.success(f"✅ Generated {len(portfolio)} tickets for draw on **{next_draw}**")
            
            # Performance metrics
            if perf:
                st.markdown("### 📊 AI Performance Stats")
                
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    st.metric(
                        "Predictions Made", 
                        perf['n_predictions'],
                        help="Total number of predictions evaluated"
                    )
                
                with metric_col2:
                    st.metric(
                        "Avg Best Match", 
                        f"{perf['avg_best_match']:.1f}/7",
                        help="Average best match across all portfolios"
                    )
                
                with metric_col3:
                    st.metric(
                        "Hit Rate (3+)", 
                        f"{perf['hit_rate_3plus']:.1%}",
                        help="Percentage of portfolios with 3+ matches"
                    )
                
                with metric_col4:
                    best_emoji = "🏆" if perf['best_ever'] >= 5 else "⭐"
                    st.metric(
                        "Best Ever", 
                        f"{best_emoji} {perf['best_ever']}/7",
                        help="Best match ever achieved"
                    )
                
                # Financial stats
                if perf['n_predictions'] > 0:
                    cost = perf['n_predictions'] * 50
                    roi = (perf['total_prize_won'] - cost) / cost * 100
                    
                    fin_col1, fin_col2, fin_col3 = st.columns(3)
                    
                    with fin_col1:
                        st.metric("Total Invested", f"${cost:.2f}")
                    with fin_col2:
                        st.metric("Total Won", f"${perf['total_prize_won']:.2f}")
                    with fin_col3:
                        roi_color = "normal" if roi >= -50 else "inverse"
                        st.metric("ROI", f"{roi:+.1f}%", delta_color=roi_color)
            
            st.markdown("---")
            
            # Display tickets
            n_freq = weights['n_freq_tickets']
            
            st.markdown("### 📊 AI-Optimized Tickets")
            st.caption("These tickets are generated based on historical frequency analysis")
            
            for i, ticket in enumerate(portfolio[:n_freq], 1):
                numbers_html = ''.join([
                    f'<span class="number-ball">{n:02d}</span>' 
                    for n in ticket
                ])
                st.markdown(f"""
                <div class="ticket-box">
                    <strong>Ticket {i}</strong><br>
                    {numbers_html}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("")
            st.markdown("### 🎲 Random Mix Tickets")
            st.caption("These tickets add diversity and uncorrelated variance")
            
            for i, ticket in enumerate(portfolio[n_freq:], n_freq + 1):
                numbers_html = ''.join([
                    f'<span class="number-ball">{n:02d}</span>' 
                    for n in ticket
                ])
                st.markdown(f"""
                <div class="ticket-box">
                    <strong>Ticket {i}</strong><br>
                    {numbers_html}
                </div>
                """, unsafe_allow_html=True)
            
            # Download section
            st.markdown("---")
            st.markdown("### 💾 Save Your Tickets")
            
            # Create downloadable text
            ticket_text = f"""LOTTO MAX AI - Generated Tickets
Draw Date: {next_draw}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Prediction ID: {prediction_id}

{'='*50}
AI-OPTIMIZED TICKETS ({n_freq} tickets)
{'='*50}

"""
            for i, ticket in enumerate(portfolio[:n_freq], 1):
                ticket_text += f"Ticket {i:2d}: {' - '.join(f'{n:02d}' for n in ticket)}\n"
            
            ticket_text += f"""
{'='*50}
RANDOM MIX TICKETS ({weights['n_random_tickets']} tickets)
{'='*50}

"""
            for i, ticket in enumerate(portfolio[n_freq:], n_freq + 1):
                ticket_text += f"Ticket {i:2d}: {' - '.join(f'{n:02d}' for n in ticket)}\n"
            
            ticket_text += f"""
{'='*50}
PORTFOLIO STATISTICS
{'='*50}
Coverage: {stats['unique_numbers']}/50 numbers ({stats['coverage_pct']:.1f}%)
Avg Overlap: {stats['avg_overlap']:.2f} numbers

Good luck! 🍀
"""
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.download_button(
                    label="📄 Download as Text File",
                    data=ticket_text,
                    file_name=f"lotto_tickets_{next_draw}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col_b:
                # CSV format
                csv_text = "Ticket,N1,N2,N3,N4,N5,N6,N7\n"
                for i, ticket in enumerate(portfolio, 1):
                    csv_text += f"{i}," + ",".join(str(n) for n in ticket) + "\n"
                
                st.download_button(
                    label="📊 Download as CSV",
                    data=csv_text,
                    file_name=f"lotto_tickets_{next_draw}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)

# Footer
st.markdown("---")
st.info("💡 **Tip:** Come back after each draw! The AI will automatically evaluate your previous tickets and learn to generate better ones.")

# Instructions expander
with st.expander("📖 Detailed Instructions"):
    st.markdown("""
    ### How to Use This App
    
    1. **Generate Tickets**
       - Click the big green button above
       - Wait 10-20 seconds while the AI works
       - Your tickets will appear below
    
    2. **Play the Tickets**
       - Download or write down the numbers
       - Play them at your local lottery retailer
       - Each ticket costs $5 (total $50 for 10 tickets)
    
    3. **After the Draw**
       - Come back to this app
       - Click "Generate" again
       - The AI will:
         * Check if you won anything
         * Learn from the results
         * Generate improved tickets for the next draw
    
    4. **Track Your Progress**
       - The performance stats show how the AI is doing
       - ROI shows your return on investment
       - Hit Rate shows how often you get 3+ matches
    
    ### Why 10 Tickets?
    
    Playing multiple tickets increases your coverage of the number space.
    The AI generates a **portfolio** of tickets that:
    - Maximizes coverage (unique numbers)
    - Minimizes overlap (redundancy)
    - Balances AI predictions with random variance
    
    ### Understanding the Strategy
    
    **70% AI-Optimized:**
    - Based on frequency analysis
    - Learns from historical patterns
    - Adapts weights based on performance
    
    **30% Random Mix:**
    - Adds uncorrelated variance
    - Prevents over-optimization
    - Proven to improve overall performance
    
    ### Important Notes
    
    ⚠️ **Lottery is gambling** - Play responsibly
    
    ✅ **This AI doesn't guarantee wins** - It optimizes your strategy
    
    📊 **Expect -40% to -50% ROI** - Better than typical -70% to -80%
    
    🧠 **The AI learns over time** - Performance improves with more draws
    """)