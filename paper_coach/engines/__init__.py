"""Recommendation engines for paper analysis."""

from .rule_based import RecommendationEngine
from .agentic import AgenticRecommendationEngine

__all__ = ["RecommendationEngine", "AgenticRecommendationEngine"]
