"""
Prediction tracking and performance monitoring system
Implements online learning with historical feedback
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from lotto_ai.config import DB_PATH

class PredictionTracker:
    """
    Track predictions and outcomes for continuous learning
    """
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._ensure_tracking_tables()
    
    def _ensure_tracking_tables(self):
        """Create tracking tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Predictions table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            target_draw_date TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            model_version TEXT,
            portfolio_size INTEGER,
            tickets TEXT NOT NULL,  -- JSON array of tickets
            metadata TEXT,  -- JSON object with model params
            evaluated BOOLEAN DEFAULT 0
        )
        """)
        
        # Results table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS prediction_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL,
            actual_numbers TEXT NOT NULL,  -- JSON array
            evaluated_at TEXT NOT NULL,
            best_match INTEGER,
            total_matches INTEGER,
            prize_value REAL,
            ticket_matches TEXT,  -- JSON array of matches per ticket
            FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
        )
        """)
        
        # Model performance tracking
        cur.execute("""
        CREATE TABLE IF NOT EXISTS model_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            window_size INTEGER,  -- last N predictions
            avg_best_match REAL,
            avg_total_matches REAL,
            avg_prize_value REAL,
            hit_rate_3plus REAL,  -- % of portfolios with 3+ matches
            metadata TEXT
        )
        """)
        
        # Adaptive weights table (for learning)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS adaptive_weights (
            weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            weight_type TEXT NOT NULL,  -- 'frequency', 'random', etc.
            weight_value REAL NOT NULL,
            performance_score REAL,
            n_observations INTEGER DEFAULT 0
        )
        """)
        
        conn.commit()
        conn.close()
    
    def save_prediction(self, target_draw_date, strategy_name, tickets, 
                       model_version="1.0", metadata=None):
        """
        Save a prediction for future evaluation
        
        Args:
            target_draw_date: Date of the draw we're predicting (YYYY-MM-DD)
            strategy_name: Name of strategy used
            tickets: List of tickets (each ticket is a list of 7 numbers)
            model_version: Version identifier
            metadata: Dict of additional parameters
        
        Returns:
            prediction_id
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        INSERT INTO predictions 
        (created_at, target_draw_date, strategy_name, model_version, 
         portfolio_size, tickets, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            target_draw_date,
            strategy_name,
            model_version,
            len(tickets),
            json.dumps(tickets),
            json.dumps(metadata or {})
        ))
        
        prediction_id = cur.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Prediction saved (ID: {prediction_id}) for draw {target_draw_date}")
        return prediction_id
    
    def evaluate_prediction(self, prediction_id, actual_numbers):
        """
        Evaluate a prediction against actual draw results
        
        Args:
            prediction_id: ID from save_prediction
            actual_numbers: List of 7 winning numbers
        
        Returns:
            Dict with evaluation metrics
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Get prediction
        cur.execute("""
        SELECT tickets, strategy_name FROM predictions 
        WHERE prediction_id = ?
        """, (prediction_id,))
        
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Prediction {prediction_id} not found")
        
        tickets = json.loads(row[0])
        strategy_name = row[1]
        
        # Calculate matches for each ticket
        ticket_matches = []
        for ticket in tickets:
            matches = len(set(ticket) & set(actual_numbers))
            ticket_matches.append(matches)
        
        best_match = max(ticket_matches)
        total_matches = sum(ticket_matches)
        prize_value = self._calculate_prize_value(ticket_matches)
        
        # Save results
        cur.execute("""
        INSERT INTO prediction_results
        (prediction_id, actual_numbers, evaluated_at, best_match, 
         total_matches, prize_value, ticket_matches)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_id,
            json.dumps(actual_numbers),
            datetime.now().isoformat(),
            best_match,
            total_matches,
            prize_value,
            json.dumps(ticket_matches)
        ))
        
        # Mark prediction as evaluated
        cur.execute("""
        UPDATE predictions SET evaluated = 1 
        WHERE prediction_id = ?
        """, (prediction_id,))
        
        conn.commit()
        conn.close()
        
        result = {
            'prediction_id': prediction_id,
            'strategy_name': strategy_name,
            'best_match': best_match,
            'total_matches': total_matches,
            'prize_value': prize_value,
            'ticket_matches': ticket_matches
        }
        
        print(f"✅ Prediction {prediction_id} evaluated:")
        print(f"   Best match: {best_match}/7")
        print(f"   Total matches: {total_matches}")
        print(f"   Prize value: ${prize_value:.2f}")
        
        return result
    
    def _calculate_prize_value(self, matches_list):
        """Calculate total prize value for all tickets"""
        prize_table = {
            7: 10_000_000,
            6: 100_000,
            5: 1_500,
            4: 50,
            3: 20
        }
        return sum(prize_table.get(m, 0) for m in matches_list)
    
    def get_unevaluated_predictions(self):
        """Get all predictions that haven't been evaluated yet"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        SELECT prediction_id, target_draw_date, strategy_name, tickets
        FROM predictions
        WHERE evaluated = 0
        ORDER BY target_draw_date
        """)
        
        results = []
        for row in cur.fetchall():
            results.append({
                'prediction_id': row[0],
                'target_draw_date': row[1],
                'strategy_name': row[2],
                'tickets': json.loads(row[3])
            })
        
        conn.close()
        return results
    
    def get_strategy_performance(self, strategy_name, window=50):
        """
        Get performance statistics for a strategy
        
        Args:
            strategy_name: Name of strategy
            window: Number of recent predictions to analyze
        
        Returns:
            Dict with performance metrics
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
        SELECT 
            pr.best_match,
            pr.total_matches,
            pr.prize_value,
            pr.ticket_matches
        FROM prediction_results pr
        JOIN predictions p ON pr.prediction_id = p.prediction_id
        WHERE p.strategy_name = ? AND p.evaluated = 1
        ORDER BY pr.evaluated_at DESC
        LIMIT ?
        """, (strategy_name, window))
        
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        best_matches = [r[0] for r in rows]
        total_matches = [r[1] for r in rows]
        prize_values = [r[2] for r in rows]
        
        # Calculate 3+ hit rate
        hit_3plus = sum(1 for r in rows if r[0] >= 3) / len(rows)
        
        return {
            'n_predictions': len(rows),
            'avg_best_match': sum(best_matches) / len(rows),
            'avg_total_matches': sum(total_matches) / len(rows),
            'avg_prize_value': sum(prize_values) / len(rows),
            'hit_rate_3plus': hit_3plus,
            'best_ever': max(best_matches),
            'total_prize_won': sum(prize_values)
        }
    
    def auto_evaluate_pending(self):
        """
        Automatically evaluate predictions where draw results are available
        """
        from lotto_ai.features.features import load_draws
        
        # Get all unevaluated predictions
        pending = self.get_unevaluated_predictions()
        
        if not pending:
            print("✅ No pending predictions to evaluate")
            return
        
        # Load actual draws
        df_draws = load_draws()
        
        evaluated_count = 0
        for pred in pending:
            target_date = pred['target_draw_date']
            
            # Check if draw exists
            draw = df_draws[df_draws['draw_date'] == target_date]
            
            if not draw.empty:
                actual_numbers = [
                    int(draw.iloc[0][f'n{i}']) for i in range(1, 8)
                ]
                
                self.evaluate_prediction(pred['prediction_id'], actual_numbers)
                evaluated_count += 1
        
        if evaluated_count > 0:
            print(f"\n✅ Auto-evaluated {evaluated_count} predictions")
        else:
            print("⏳ No new draw results available yet")