"""
Production model - imports from core.models
Kept for backward compatibility
"""
from lotto_ai.core.models import (
    generate_adaptive_portfolio,
    portfolio_statistics,
    generate_ticket_safe,
    frequency_probability
)

__all__ = [
    'generate_adaptive_portfolio',
    'portfolio_statistics',
    'generate_ticket_safe',
    'frequency_probability'
]