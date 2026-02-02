"""Recommendation engines for paper analysis."""

from .rule_based import RecommendationEngine
from .agentic import AgenticRecommendationEngine
from .smart_search import SmartSearchEngine

__all__ = ["RecommendationEngine", "AgenticRecommendationEngine", "SmartSearchEngine"]
