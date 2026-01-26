"""
Database layer using SQLAlchemy for safer access
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from lotto_ai.config import DB_PATH, logger
import json

Base = declarative_base()

class Draw(Base):
    __tablename__ = 'draws'
    
    draw_date = Column(String, primary_key=True)
    n1 = Column(Integer)
    n2 = Column(Integer)
    n3 = Column(Integer)
    n4 = Column(Integer)
    n5 = Column(Integer)
    n6 = Column(Integer)
    n7 = Column(Integer)
    bonus = Column(Integer)

class Prediction(Base):
    __tablename__ = 'predictions'
    
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(String, nullable=False)
    target_draw_date = Column(String, nullable=False)
    strategy_name = Column(String, nullable=False)
    model_version = Column(String)
    portfolio_size = Column(Integer)
    tickets = Column(Text, nullable=False)  # JSON
    model_metadata = Column(Text)  # ✅ RENAMED from 'metadata'
    evaluated = Column(Boolean, default=False)
    
    results = relationship("PredictionResult", back_populates="prediction")

class PredictionResult(Base):
    __tablename__ = 'prediction_results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey('predictions.prediction_id'))
    actual_numbers = Column(Text, nullable=False)  # JSON
    evaluated_at = Column(String, nullable=False)
    best_match = Column(Integer)
    total_matches = Column(Integer)
    prize_value = Column(Float)
    ticket_matches = Column(Text)  # JSON
    
    prediction = relationship("Prediction", back_populates="results")

class PlayedTicket(Base):
    __tablename__ = 'played_tickets'
    
    play_id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey('predictions.prediction_id'))
    ticket_numbers = Column(Text, nullable=False)  # JSON
    played_at = Column(String, nullable=False)
    draw_date = Column(String, nullable=False)

class AdaptiveWeight(Base):
    __tablename__ = 'adaptive_weights'
    
    weight_id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(String, nullable=False)
    strategy_name = Column(String, nullable=False)
    weight_type = Column(String, nullable=False)
    weight_value = Column(Float, nullable=False)
    performance_score = Column(Float)
    n_observations = Column(Integer, default=0)

# Database engine and session
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def get_session():
    """Get database session"""
    return SessionLocal()