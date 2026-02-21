"""
Adaptive learning - v3.0
Tracks portfolio STRATEGY performance, not lottery patterns.
"""
from datetime import datetime
import json
from lotto_ai.core.db import get_session, AdaptiveWeight
from lotto_ai.core.tracker import PredictionTracker
from lotto_ai.config import logger


class AdaptiveLearner:

    def __init__(self):
        self.tracker = PredictionTracker()
        self._initialize_weights()

    def _initialize_weights(self):
        session = get_session()
        try:
            count = session.query(AdaptiveWeight).count()
            if count == 0:
                defaults = [
                    ('coverage_optimized', 'coverage_ratio', 1.0, 0.0, 0),
                    ('coverage_optimized', 'random_ratio', 0.0, 0.0, 0),
                ]
                for strategy, wtype, value, score, n_obs in defaults:
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
        except Exception as e:
            session.rollback()
            logger.error(f"Error initializing weights: {e}")
        finally:
            session.close()

    def get_current_weights(self, strategy_name='coverage_optimized'):
        session = get_session()
        try:
            weights = {}
            for weight_type in ['coverage_ratio', 'random_ratio']:
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
                    default = 1.0 if weight_type == 'coverage_ratio' else 0.0
                    weights[weight_type] = {
                        'value': default, 'performance': 0.0, 'n_obs': 0
                    }

            # Backward compatibility aliases
            weights['frequency_ratio'] = weights.get('coverage_ratio',
                                                      {'value': 1.0})
            weights['random_ratio'] = weights.get('random_ratio',
                                                   {'value': 0.0})
            return weights
        finally:
            session.close()

    def update_weights(self, strategy_name='coverage_optimized', window=20):
        perf = self.tracker.get_strategy_performance(strategy_name, window)

        if not perf or perf['n_predictions'] < 3:
            logger.info("Not enough data to update weights")
            return None

        current = self.get_current_weights(strategy_name)
        vs_random = perf.get('vs_random', 1.0)
        current_coverage = current.get('coverage_ratio', {}).get('value', 1.0)

        if vs_random >= 1.05:
            new_coverage = min(1.0, current_coverage + 0.05)
        elif vs_random < 0.90:
            new_coverage = max(0.50, current_coverage - 0.05)
        else:
            new_coverage = current_coverage

        new_random = 1.0 - new_coverage

        session = get_session()
        try:
            for wtype, value in [('coverage_ratio', new_coverage),
                                  ('random_ratio', new_random)]:
                weight = AdaptiveWeight(
                    updated_at=datetime.now().isoformat(),
                    strategy_name=strategy_name,
                    weight_type=wtype,
                    weight_value=value,
                    performance_score=perf['hit_rate_3plus'],
                    n_observations=perf['n_predictions']
                )
                session.add(weight)
            session.commit()

            logger.info(f"Weights updated: {new_coverage:.0%} coverage / "
                        f"{new_random:.0%} random")

            return {
                'frequency_ratio': new_coverage,
                'random_ratio': new_random,
                'performance_score': perf['hit_rate_3plus'],
                'n_observations': perf['n_predictions'],
                'vs_random': vs_random
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating weights: {e}")
            return None
        finally:
            session.close()

    def get_learning_history(self, strategy_name='coverage_optimized'):
        session = get_session()
        try:
            weights = session.query(AdaptiveWeight).filter_by(
                strategy_name=strategy_name
            ).order_by(AdaptiveWeight.updated_at).all()

            return [{
                'timestamp': w.updated_at,
                'weight_type': w.weight_type,
                'value': w.weight_value,
                'performance': w.performance_score,
                'n_obs': w.n_observations
            } for w in weights]
        finally:
            session.close()