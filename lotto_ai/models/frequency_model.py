"""
Pure frequency-based model using Maximum Likelihood Estimation
No overfitting, just empirical probability distribution
"""
import pandas as pd
import numpy as np

def frequency_probability(features, smoothing=0.5):
    """
    Calculate probability using Laplace smoothing
    
    P(number) = (hits + α) / (total_draws + α * n_numbers)
    
    Args:
        smoothing: Laplace smoothing parameter (prevents zero probabilities)
    """
    grouped = features.groupby("number")["hit"].agg(["sum", "count"])
    
    n_numbers = len(grouped)
    
    # Laplace smoothing
    grouped["freq_prob"] = (
        (grouped["sum"] + smoothing) /
        (grouped["count"] + smoothing * n_numbers)
    )
    
    return grouped["freq_prob"]

def gap_weighted_probability(features, decay=0.95):
    """
    Weight recent draws more heavily using exponential decay
    
    More recent gaps → higher probability
    """
    latest = features.groupby("number").apply(
        lambda g: g.nlargest(1, "draw_index")["gap"].values[0]
    )
    
    # Convert gap to recency weight
    # Smaller gap = more recent = lower weight
    # We want LARGER gaps to have HIGHER probability (overdue numbers)
    weights = latest.apply(lambda gap: decay ** (-gap))
    
    # Normalize
    return weights / weights.sum()

def hot_cold_probability(features, window=20):
    """
    Combine 'hot' (recently frequent) and 'cold' (overdue) numbers
    """
    recent = features[features["draw_index"] >= features["draw_index"].max() - window]
    
    hot = recent.groupby("number")["hit"].sum()
    cold = features.groupby("number")["gap"].last()
    
    # Normalize both
    hot_norm = hot / hot.sum()
    cold_norm = cold / cold.sum()
    
    # 50/50 blend
    return 0.5 * hot_norm + 0.5 * cold_norm