"""
Feature engineering for Loto Serbia - v3.0
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from lotto_ai.config import DB_PATH, BASE_DIR, NUMBER_RANGE, NUMBERS_PER_DRAW

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

NUMBERS = range(NUMBER_RANGE[0], NUMBER_RANGE[1] + 1)


def load_draws():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM draws ORDER BY draw_date", conn)
    conn.close()
    return df


def load_draws_as_lists():
    df = load_draws()
    draws = []
    for _, row in df.iterrows():
        numbers = [row[f'n{i}'] for i in range(1, NUMBERS_PER_DRAW + 1)]
        draws.append({
            'date': row['draw_date'],
            'numbers': sorted(numbers)
        })
    return draws


def build_feature_matrix(window=10):
    """
    Build descriptive feature matrix.
    NOTE: These features describe PAST behavior only.
    """
    df = load_draws()

    if len(df) == 0:
        return pd.DataFrame()

    records = []

    for number in NUMBERS:
        appeared = df[
            (df[[f"n{i}" for i in range(1, NUMBERS_PER_DRAW + 1)]] == number).any(axis=1)
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


def get_number_summary(n_recent=20):
    """
    Get a summary of each number's recent behavior.
    Useful for display purposes - NOT for prediction.

    Args:
        n_recent: Number of recent draws to analyze
    """
    df = load_draws()
    if len(df) == 0:
        return {}

    recent = df.tail(n_recent)
    all_data = df

    summary = {}
    expected_freq = NUMBERS_PER_DRAW / (NUMBER_RANGE[1] - NUMBER_RANGE[0] + 1)

    for num in NUMBERS:
        # Overall frequency
        total_appearances = 0
        for _, row in all_data.iterrows():
            drawn = [int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)]
            if num in drawn:
                total_appearances += 1

        overall_freq = total_appearances / len(all_data) if len(all_data) > 0 else 0

        # Recent frequency
        recent_appearances = 0
        for _, row in recent.iterrows():
            drawn = [int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)]
            if num in drawn:
                recent_appearances += 1

        recent_freq = recent_appearances / len(recent) if len(recent) > 0 else 0

        # Current gap
        last_seen = None
        for idx in range(len(all_data) - 1, -1, -1):
            row = all_data.iloc[idx]
            drawn = [int(row[f'n{i}']) for i in range(1, NUMBERS_PER_DRAW + 1)]
            if num in drawn:
                last_seen = idx
                break

        current_gap = len(all_data) - 1 - last_seen if last_seen is not None else len(all_data)

        # Status label
        if recent_freq > expected_freq * 1.3:
            status = 'HOT 🔥'
        elif recent_freq < expected_freq * 0.7:
            status = 'COLD ❄️'
        else:
            status = 'NORMAL'

        summary[num] = {
            'number': num,
            'total_appearances': int(total_appearances),
            'overall_frequency': float(overall_freq),
            'recent_frequency': float(recent_freq),
            'expected_frequency': float(expected_freq),
            'deviation': float(overall_freq - expected_freq),
            'current_gap': int(current_gap),
            'status': status,
        }

    return summary