"""
Prediction tracking - v3.0
"""
from datetime import datetime
import json
import numpy as np
from lotto_ai.core.db import get_session, Prediction, PredictionResult, PlayedTicket, Draw
from lotto_ai.config import logger, PRIZE_TABLE, NUMBERS_PER_DRAW
from lotto_ai.core.math_engine import match_probability_at_least


class PredictionTracker:
    """Track predictions and outcomes"""

    def save_prediction(self, target_draw_date, strategy_name, tickets,
                        model_version="3.0", metadata=None):
        session = get_session()
        try:
            # Serialize metadata safely
            if metadata is not None:
                meta_str = json.dumps(metadata, default=str)
            else:
                meta_str = json.dumps({})

            prediction = Prediction(
                created_at=datetime.now().isoformat(),
                target_draw_date=target_draw_date,
                strategy_name=strategy_name,
                model_version=model_version,
                portfolio_size=len(tickets),
                tickets=json.dumps(tickets),
                model_metadata=meta_str,
                evaluated=False
            )
            session.add(prediction)
            session.commit()

            pred_id = prediction.prediction_id
            logger.info(f"Saved prediction {pred_id} for {target_draw_date}")
            return pred_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving prediction: {e}")
            return None
        finally:
            session.close()

    def evaluate_prediction(self, prediction_id, actual_numbers):
        session = get_session()
        try:
            prediction = session.query(Prediction).filter_by(
                prediction_id=prediction_id
            ).first()
            if not prediction:
                logger.error(f"Prediction {prediction_id} not found")
                return None

            tickets = json.loads(prediction.tickets)
            ticket_matches = [
                len(set(t) & set(actual_numbers)) for t in tickets
            ]

            best_match = max(ticket_matches)
            total_matches = sum(ticket_matches)
            prize_value = self._calculate_prize_value(ticket_matches)

            result = PredictionResult(
                prediction_id=prediction_id,
                actual_numbers=json.dumps(actual_numbers),
                evaluated_at=datetime.now().isoformat(),
                best_match=best_match,
                total_matches=total_matches,
                prize_value=prize_value,
                ticket_matches=json.dumps(ticket_matches)
            )
            session.add(result)

            prediction.evaluated = True
            session.commit()

            logger.info(f"Evaluated prediction {prediction_id}: "
                        f"{best_match}/7 best match")
            return {
                'prediction_id': prediction_id,
                'best_match': best_match,
                'total_matches': total_matches,
                'prize_value': prize_value,
                'ticket_matches': ticket_matches
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error evaluating prediction: {e}")
            return None
        finally:
            session.close()

    def auto_evaluate_pending(self):
        session = get_session()
        try:
            pending = session.query(Prediction).filter_by(evaluated=False).all()

            if not pending:
                logger.info("Auto-evaluated 0 predictions")
                return 0

            evaluated_count = 0
            for pred in pending:
                draw = session.query(Draw).filter_by(
                    draw_date=pred.target_draw_date
                ).first()

                if draw:
                    actual_numbers = draw.get_numbers()
                    self.evaluate_prediction(pred.prediction_id, actual_numbers)
                    evaluated_count += 1

            logger.info(f"Auto-evaluated {evaluated_count} predictions")
            return evaluated_count
        finally:
            session.close()

    def get_strategy_performance(self, strategy_name, window=50):
        session = get_session()
        try:
            results = session.query(PredictionResult).join(Prediction).filter(
                Prediction.strategy_name == strategy_name,
                Prediction.evaluated == True
            ).order_by(PredictionResult.evaluated_at.desc()).limit(window).all()

            if not results:
                logger.info("Not enough data to track performance")
                return None

            best_matches = [r.best_match for r in results]
            total_matches = [r.total_matches for r in results]
            prize_values = [r.prize_value for r in results]

            # Get portfolio sizes
            n_tickets_list = []
            for r in results:
                pred = session.query(Prediction).filter_by(
                    prediction_id=r.prediction_id
                ).first()
                if pred and pred.portfolio_size:
                    n_tickets_list.append(pred.portfolio_size)

            hit_3plus = (sum(1 for b in best_matches if b >= 3) / len(results)
                         if results else 0)

            avg_tickets = float(np.mean(n_tickets_list)) if n_tickets_list else 10
            expected_3plus_rate = 1 - (
                (1 - match_probability_at_least(3)) ** avg_tickets
            )

            vs_random = (hit_3plus / expected_3plus_rate
                         if expected_3plus_rate > 0 else 1.0)

            return {
                'n_predictions': len(results),
                'avg_best_match': float(np.mean(best_matches)),
                'avg_total_matches': float(np.mean(total_matches)),
                'avg_prize_value': float(np.mean(prize_values)),
                'hit_rate_3plus': hit_3plus,
                'expected_3plus_rate': expected_3plus_rate,
                'vs_random': vs_random,
                'best_ever': max(best_matches),
                'total_prize_won': sum(prize_values),
                'avg_tickets_per_prediction': avg_tickets
            }
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return None
        finally:
            session.close()

    def _calculate_prize_value(self, matches_list):
        return sum(PRIZE_TABLE.get(m, 0) for m in matches_list)


class PlayedTicketsTracker:

    def save_played_tickets(self, prediction_id, tickets, draw_date):
        session = get_session()
        try:
            for ticket in tickets:
                played = PlayedTicket(
                    prediction_id=prediction_id,
                    ticket_numbers=json.dumps(ticket),
                    played_at=datetime.now().isoformat(),
                    draw_date=draw_date
                )
                session.add(played)
            session.commit()
            logger.info(f"Saved {len(tickets)} played tickets for {draw_date}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving played tickets: {e}")
        finally:
            session.close()