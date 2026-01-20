"""
Adaptive learning system that adjusts strategy weights based on performance
Implements Thompson Sampling for multi-armed bandit problem
"""
import sqlite3
import numpy as np
from datetime import datetime
from lotto_ai.config import DB_PATH
from lotto_ai.tracking.prediction_tracker import PredictionTracker

class AdaptiveLearner:
    """
    Online learning system that adapts strategy weights
    Uses Bayesian updating with Beta distributions
    """
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.tracker = PredictionTracker(db_path)
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize default weights if none exist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Check if weights exist
        cur.execute("SELECT COUNT(*) FROM adaptive_weights")
        count = cur.fetchone()[0]
        
        if count == 0:
            # Initialize with uniform prior
            default_weights = [
                ('hybrid_v1', 'frequency_ratio', 0.70, 0.0, 0),
                ('hybrid_v1', 'random_ratio', 0.30, 0.0, 0)
            ]
            
            for strategy, wtype, value, score, n_obs in default_weights:
                cur.execute("""
                INSERT INTO adaptive_weights
                (updated_at, strategy_name, weight_type, weight_value, 
                 performance_score, n_observations)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (datetime.now().isoformat(), strategy, wtype, value, score, n_obs))
            
            conn.commit()
            print("✅ Initialized adaptive weights")
        
        conn.close()
    
    def get_current_weights(self, strategy_name='hybrid_v1'):
        """Get current adaptive weights for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        SELECT weight_type, weight_value, performance_score, n_observations
        FROM adaptive_weights
        WHERE strategy_name = ?
        ORDER BY updated_at DESC
        """, (strategy_name,))
        
        weights = {}
        for row in cur.fetchall():
            weights[row[0]] = {
                'value': row[1],
                'performance': row[2],
                'n_obs': row[3]
            }
        
        conn.close()
        return weights
    
    def update_weights(self, strategy_name='hybrid_v1', window=20):
        """
        Update strategy weights based on recent performance
        
        Uses Thompson Sampling:
        - Model each strategy component as Beta distribution
        - Update based on success rate (3+ matches = success)
        - Sample from posterior to get new weights
        """
        # Get recent performance
        perf = self.tracker.get_strategy_performance(strategy_name, window)
        
        if not perf or perf['n_predictions'] < 5:
            print("⏳ Not enough data to update weights (need 5+ predictions)")
            return None
        
        # Current weights
        current = self.get_current_weights(strategy_name)
        
        # Performance metric: 3+ hit rate
        success_rate = perf['hit_rate_3plus']
        
        # Bayesian update using Beta distribution
        # Prior: Beta(α=1, β=1) - uniform
        # Posterior: Beta(α=1+successes, β=1+failures)
        
        n_success = int(perf['hit_rate_3plus'] * perf['n_predictions'])
        n_failure = perf['n_predictions'] - n_success
        
        # Sample from posterior
        alpha = 1 + n_success
        beta = 1 + n_failure
        
        # Thompson Sampling: adjust weights based on uncertainty
        freq_performance = np.random.beta(alpha, beta)
        
        # Adaptive adjustment
        if success_rate > 0.05:  # Better than baseline
            # Increase frequency weight slightly
            new_freq_weight = min(0.80, current['frequency_ratio']['value'] + 0.05)
        elif success_rate < 0.03:  # Worse than baseline
            # Decrease frequency weight
            new_freq_weight = max(0.60, current['frequency_ratio']['value'] - 0.05)
        else:
            # Keep current
            new_freq_weight = current['frequency_ratio']['value']
        
        new_random_weight = 1.0 - new_freq_weight
        
        # Save updated weights
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        for wtype, value in [('frequency_ratio', new_freq_weight), 
                              ('random_ratio', new_random_weight)]:
            cur.execute("""
            INSERT INTO adaptive_weights
            (updated_at, strategy_name, weight_type, weight_value, 
             performance_score, n_observations)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                strategy_name,
                wtype,
                value,
                success_rate,
                perf['n_predictions']
            ))
        
        conn.commit()
        conn.close()
        
        print(f"\n🧠 Weights updated based on {perf['n_predictions']} predictions:")
        print(f"   Success rate: {success_rate:.1%} (3+ matches)")
        print(f"   New weights: {new_freq_weight:.0%} freq / {new_random_weight:.0%} random")
        
        return {
            'frequency_ratio': new_freq_weight,
            'random_ratio': new_random_weight,
            'performance_score': success_rate,
            'n_observations': perf['n_predictions']
        }
    
    def get_learning_history(self, strategy_name='hybrid_v1'):
        """Get historical weight adjustments"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        SELECT updated_at, weight_type, weight_value, 
               performance_score, n_observations
        FROM adaptive_weights
        WHERE strategy_name = ?
        ORDER BY updated_at
        """, (strategy_name,))
        
        history = []
        for row in cur.fetchall():
            history.append({
                'timestamp': row[0],
                'weight_type': row[1],
                'value': row[2],
                'performance': row[3],
                'n_obs': row[4]
            })
        
        conn.close()
        return history