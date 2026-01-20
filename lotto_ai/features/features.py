import sqlite3
import pandas as pd
from lotto_ai.config import DB_PATH

NUMBERS = range(1, 51)

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM draws ORDER BY draw_date", conn)
    conn.close()
    return df


def build_feature_matrix(window=10):
    df = load_draws()

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
                "freq": len(past_hits) / i,
                "gap": i - past_hits[-1] if past_hits else i,
                "rolling_freq": sum(h >= i - window for h in past_hits) / window,
                "hit": int(i in hits)
            })

    return pd.DataFrame(records)
