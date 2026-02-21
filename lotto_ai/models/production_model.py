"""
Production model - redirects to core.models
"""
from lotto_ai.core.models import (
    generate_optimized_portfolio,
    generate_adaptive_portfolio,
    frequency_analysis
)
from lotto_ai.core.coverage_optimizer import portfolio_statistics

__all__ = [
    'generate_optimized_portfolio',
    'generate_adaptive_portfolio',
    'portfolio_statistics',
    'frequency_analysis'
]