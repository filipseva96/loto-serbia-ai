"""
FastAPI backend for Railway deployment
Handles scraping and evaluation separately from UI
"""
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from lotto_ai.core.db import init_db
from lotto_ai.core.tracker import PredictionTracker
from lotto_ai.scraper.fetch_draws import scrape_recent_draws
from lotto_ai.config import logger, SCRAPING_ENABLED
import os

# Initialize database
init_db()

app = FastAPI(title="Lotto Max AI Backend")

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "scraping_enabled": SCRAPING_ENABLED,
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "local")
    }

@app.post("/scrape")
def trigger_scrape(background_tasks: BackgroundTasks, days_back: int = 30):
    """Trigger scraping in background"""
    if not SCRAPING_ENABLED:
        return JSONResponse(
            status_code=403,
            content={"error": "Scraping disabled in this environment"}
        )
    
    background_tasks.add_task(scrape_recent_draws, days_back)
    return {"message": f"Scraping started (last {days_back} days)"}

@app.post("/evaluate")
def evaluate_predictions():
    """Evaluate pending predictions"""
    tracker = PredictionTracker()
    count = tracker.auto_evaluate_pending()
    return {"evaluated": count}

@app.get("/performance/{strategy}")
def get_performance(strategy: str, window: int = 50):
    """Get strategy performance"""
    tracker = PredictionTracker()
    perf = tracker.get_strategy_performance(strategy, window)
    return perf or {"error": "No data available"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)