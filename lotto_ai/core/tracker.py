"""
Prediction tracking with SQLAlchemy
"""
from datetime import datetime
import json
from lotto_ai.core.db import get_session, Prediction, PredictionResult, PlayedTicket, Draw
from lotto_ai.config import logger

class PredictionTracker:
    """Track predictions and outcomes"""
    
    def save_prediction(self, target_draw_date, strategy_name, tickets, 
                   model_version="2.0", metadata=None):
        """Save a prediction"""
        session = get_session()
        try:
            prediction = Prediction(
                created_at=datetime.now().isoformat(),
                target_draw_date=target_draw_date,
                strategy_name=strategy_name,
                model_version=model_version,
                portfolio_size=len(tickets),
                tickets=json.dumps(tickets),
                model_metadata=json.dumps(metadata or {}),  # ✅ FIXED
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
        """Evaluate a prediction against actual results"""
        session = get_session()
        try:
            prediction = session.query(Prediction).filter_by(prediction_id=prediction_id).first()
            if not prediction:
                logger.error(f"Prediction {prediction_id} not found")
                return None
            
            tickets = json.loads(prediction.tickets)
            ticket_matches = [len(set(t) & set(actual_numbers)) for t in tickets]
            
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
            
            logger.info(f"Evaluated prediction {prediction_id}: {best_match}/7 best match")
            return {
                'prediction_id': prediction_id,
                'best_match': best_match,
                'total_matches': total_matches,
                'prize_value': prize_value
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error evaluating prediction: {e}")
            return None
        finally:
            session.close()
    
    def auto_evaluate_pending(self):
        """Auto-evaluate predictions where results are available"""
        session = get_session()
        try:
            pending = session.query(Prediction).filter_by(evaluated=False).all()
            
            if not pending:
                logger.info("No pending predictions")
                return 0
            
            evaluated_count = 0
            for pred in pending:
                draw = session.query(Draw).filter_by(draw_date=pred.target_draw_date).first()
                
                if draw:
                    actual_numbers = [draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6, draw.n7]
                    self.evaluate_prediction(pred.prediction_id, actual_numbers)
                    evaluated_count += 1
            
            logger.info(f"Auto-evaluated {evaluated_count} predictions")
            return evaluated_count
        finally:
            session.close()
    
    def get_strategy_performance(self, strategy_name, window=50):
        """Get performance statistics"""
        session = get_session()
        try:
            results = session.query(PredictionResult).join(Prediction).filter(
                Prediction.strategy_name == strategy_name,
                Prediction.evaluated == True
            ).order_by(PredictionResult.evaluated_at.desc()).limit(window).all()
            
            if not results:
                return None
            
            best_matches = [r.best_match for r in results]
            total_matches = [r.total_matches for r in results]
            prize_values = [r.prize_value for r in results]
            
            hit_3plus = sum(1 for r in results if r.best_match >= 3) / len(results)
            
            return {
                'n_predictions': len(results),
                'avg_best_match': sum(best_matches) / len(results),
                'avg_total_matches': sum(total_matches) / len(results),
                'avg_prize_value': sum(prize_values) / len(results),
                'hit_rate_3plus': hit_3plus,
                'best_ever': max(best_matches),
                'total_prize_won': sum(prize_values)
            }
        finally:
            session.close()
    
    def _calculate_prize_value(self, matches_list):
        """Calculate total prize value"""
        prize_table = {7: 10_000_000, 6: 100_000, 5: 1_500, 4: 50, 3: 20}
        return sum(prize_table.get(m, 0) for m in matches_list)

class PlayedTicketsTracker:
    """Track which tickets were actually played"""
    
    def save_played_tickets(self, prediction_id, tickets, draw_date):
        """Save played tickets"""
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