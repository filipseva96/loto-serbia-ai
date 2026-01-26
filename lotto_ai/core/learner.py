"""
Adaptive learning system using SQLAlchemy
"""
from datetime import datetime
from lotto_ai.core.db import get_session, AdaptiveWeight
from lotto_ai.core.tracker import PredictionTracker
from lotto_ai.config import logger
import numpy as np

class AdaptiveLearner:
    """
    Online learning system that adapts strategy weights
    Uses Bayesian updating with Beta distributions
    """
    
    def __init__(self):
        self.tracker = PredictionTracker()
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize default weights if none exist"""
        session = get_session()
        try:
            # Check if weights exist
            count = session.query(AdaptiveWeight).count()
            
            if count == 0:
                # Initialize with uniform prior
                default_weights = [
                    ('hybrid_v1', 'frequency_ratio', 0.70, 0.0, 0),
                    ('hybrid_v1', 'random_ratio', 0.30, 0.0, 0)
                ]
                
                for strategy, wtype, value, score, n_obs in default_weights:
                    weight = AdaptiveWeight(
                        updated_at=datetime.now().isoformat(),
                        strategy_name=strategy,
                        weight_type=wtype,
                        weight_value=value,
                        performance_score=score,
                        n_observations=n_obs
                    )
                    session.add(weight)
                
                session.commit()
                logger.info("Initialized adaptive weights")
        except Exception as e:
            session.rollback()
            logger.error(f"Error initializing weights: {e}")
        finally:
            session.close()
    
    def get_current_weights(self, strategy_name='hybrid_v1'):
        """Get current adaptive weights for a strategy"""
        session = get_session()
        try:
            # Get most recent weights for each type
            weights = {}
            
            for weight_type in ['frequency_ratio', 'random_ratio']:
                weight = session.query(AdaptiveWeight).filter_by(
                    strategy_name=strategy_name,
                    weight_type=weight_type
                ).order_by(AdaptiveWeight.updated_at.desc()).first()
                
                if weight:
                    weights[weight_type] = {
                        'value': weight.weight_value,
                        'performance': weight.performance_score,
                        'n_obs': weight.n_observations
                    }
                else:
                    # Fallback defaults
                    default_value = 0.70 if weight_type == 'frequency_ratio' else 0.30
                    weights[weight_type] = {
                        'value': default_value,
                        'performance': 0.0,
                        'n_obs': 0
                    }
            
            return weights
        finally:
            session.close()
    
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
            logger.info("Not enough data to update weights (need 5+ predictions)")
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
        current_freq = current['frequency_ratio']['value']
        
        if success_rate > 0.05:  # Better than baseline
            # Increase frequency weight slightly
            new_freq_weight = min(0.80, current_freq + 0.05)
        elif success_rate < 0.03:  # Worse than baseline
            # Decrease frequency weight
            new_freq_weight = max(0.60, current_freq - 0.05)
        else:
            # Keep current
            new_freq_weight = current_freq
        
        new_random_weight = 1.0 - new_freq_weight
        
        # Save updated weights
        session = get_session()
        try:
            for wtype, value in [('frequency_ratio', new_freq_weight), 
                                  ('random_ratio', new_random_weight)]:
                weight = AdaptiveWeight(
                    updated_at=datetime.now().isoformat(),
                    strategy_name=strategy_name,
                    weight_type=wtype,
                    weight_value=value,
                    performance_score=success_rate,
                    n_observations=perf['n_predictions']
                )
                session.add(weight)
            
            session.commit()
            
            logger.info(f"Weights updated based on {perf['n_predictions']} predictions:")
            logger.info(f"  Success rate: {success_rate:.1%} (3+ matches)")
            logger.info(f"  New weights: {new_freq_weight:.0%} freq / {new_random_weight:.0%} random")
            
            return {
                'frequency_ratio': new_freq_weight,
                'random_ratio': new_random_weight,
                'performance_score': success_rate,
                'n_observations': perf['n_predictions']
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating weights: {e}")
            return None
        finally:
            session.close()
    
    def get_learning_history(self, strategy_name='hybrid_v1'):
        """Get historical weight adjustments"""
        session = get_session()
        try:
            weights = session.query(AdaptiveWeight).filter_by(
                strategy_name=strategy_name
            ).order_by(AdaptiveWeight.updated_at).all()
            
            history = []
            for w in weights:
                history.append({
                    'timestamp': w.updated_at,
                    'weight_type': w.weight_type,
                    'value': w.weight_value,
                    'performance': w.performance_score,
                    'n_obs': w.n_observations
                })
            
            return history
        finally:
            session.close()