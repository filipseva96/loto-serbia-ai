"""
Feature engineering for statistical analysis (NOT prediction).
These features are used for lottery fairness testing and display only.
"""
import sqlite3
import pandas as pd
from pathlib import Path
import sys
from lotto_ai.config import DB_PATH, BASE_DIR, NUMBER_RANGE

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

NUMBERS = range(NUMBER_RANGE[0], NUMBER_RANGE[1] + 1)


def load_draws():
    """Load all draws from database"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM draws ORDER BY draw_date", conn)
    conn.close()
    return df


def build_feature_matrix(window=10):
    """
    Build feature matrix for statistical analysis.

    NOTE: These features are for ANALYSIS and DISPLAY, not prediction.
    In a fair lottery, none of these have predictive power.
    """
    df = load_draws()

    if len(df) == 0:
        return pd.DataFrame()

    records = []

    for number in NUMBERS:
        appeared = df[
            (df[[f"n{i}" for i in range(1, 8)]] == number).any(axis=1)
        ]
        hits = appeared.index.tolist()

        for i in range(1, len(df)):
            past_hits = [h for h in hits if h < i]
            records.append({
                "number": number,
                "draw_index": i,
                "freq": len(past_hits) / i if i > 0 else 0,
                "gap": i - past_hits[-1] if past_hits else i,
                "rolling_freq": sum(h >= i - window for h in past_hits) / window,
                "hit": int(i in hits)
            })

    return pd.DataFrame(records)


def get_number_summary():
    """
    Get a summary of each number's historical performance.
    For display purposes only.
    """
    df = load_draws()

    if len(df) == 0:
        return pd.DataFrame()

    n_draws = len(df)
    summary = []

    for number in NUMBERS:
        appeared = df[
            (df[[f"n{i}" for i in range(1, 8)]] == number).any(axis=1)
        ]

        count = len(appeared)
        frequency = count / n_draws if n_draws > 0 else 0
        expected_freq = 7 / 39  # ~0.1795

        # Last appearance
        if len(appeared) > 0:
            last_draw_idx = appeared.index[-1]
            gap = n_draws - 1 - last_draw_idx
        else:
            gap = n_draws

        # Recent performance (last 20 draws)
        recent_df = df.tail(20)
        recent_appeared = recent_df[
            (recent_df[[f"n{i}" for i in range(1, 8)]] == number).any(axis=1)
        ]
        recent_freq = len(recent_appeared) / min(20, n_draws)

        summary.append({
            'number': number,
            'total_appearances': count,
            'frequency': frequency,
            'expected_frequency': expected_freq,
            'deviation_pct': (frequency - expected_freq) / expected_freq * 100,
            'current_gap': gap,
            'recent_frequency_20': recent_freq,
            'is_hot': recent_freq > expected_freq * 1.3,
            'is_cold': recent_freq < expected_freq * 0.7,
        })

    return pd.DataFrame(summary).sort_values('number')