#!/usr/bin/env python3
"""
Recommendation Engine for Paper Implementation Coach
Decides which papers to implement based on context and prerequisites
"""

from typing import Dict, List, Optional
from ..db import KnowledgeBase
from ..integrations import ArxivHelper


class RecommendationEngine:
    """Decides which papers are worth implementing"""

    def __init__(self):
        self.kb = KnowledgeBase()
        self.arxiv = ArxivHelper()

    def analyze_paper(self, paper_query: str, user_context: Optional[Dict] = None) -> Dict:
        """
        Analyze whether a paper is worth implementing

        Args:
            paper_query: Paper title, arxiv ID, or paper_id
            user_context: Optional dict with:
                - implemented_papers: List[str] of paper_ids already implemented
                - research_goal: str describing what user wants to learn
                - time_available: str like "4-8 hours" or "a weekend"
                - expertise_level: str in ['beginner', 'intermediate', 'advanced']

        Returns:
            Dict with recommendation decision and reasoning
        """

        # Default user context
        if user_context is None:
            user_context = {
                'implemented_papers': [],
                'expertise_level': 'intermediate'
            }

        # Try to find paper in knowledge base first
        paper = self._find_paper(paper_query)

        if not paper:
            return {
                'found': False,
                'recommendation': 'unknown',
                'message': f"Paper '{paper_query}' not found in knowledge base. Try searching arxiv or add it manually.",
            }

        # Get prerequisites
        prerequisites = self.kb.get_prerequisites(paper['paper_id'])

        # Analyze
        recommendation = self._make_recommendation(paper, prerequisites, user_context)

        return recommendation

    def _find_paper(self, query: str) -> Optional[Dict]:
        """Find paper by various query methods"""

        # Try exact paper_id match
        paper = self.kb.get_paper(query)
        if paper:
            return paper

        # Try searching by title (fuzzy match)
        all_papers = self.kb.get_all_papers()
        query_lower = query.lower()

        for p in all_papers:
            if query_lower in p['title'].lower():
                return p
            if p['arxiv_id'] and query in p['arxiv_id']:
                return p

        return None

    def _make_recommendation(self, paper: Dict, prerequisites: List[Dict],
                             user_context: Dict) -> Dict:
        """Generate recommendation with reasoning"""

        implemented = set(user_context.get('implemented_papers', []))
        expertise = user_context.get('expertise_level', 'intermediate')

        # Check prerequisites
        missing_required = []
        missing_recommended = []

        for prereq in prerequisites:
            if prereq['paper_id'] not in implemented:
                if prereq['importance'] == 'required':
                    missing_required.append(prereq)
                elif prereq['importance'] == 'recommended':
                    missing_recommended.append(prereq)

        # Determine recommendation
        if missing_required:
            return self._build_not_yet_response(paper, missing_required, missing_recommended)

        if self._is_too_difficult(paper, expertise):
            return self._build_difficulty_warning(paper, expertise)

        if self._is_low_value(paper, user_context):
            return self._build_low_value_response(paper)

        # Recommend!
        return self._build_recommend_response(paper, missing_recommended, user_context)

    def _build_not_yet_response(self, paper: Dict, required: List[Dict],
                                recommended: List[Dict]) -> Dict:
        """Build 'not yet, do prerequisites first' response"""

        prereq_path = []
        for prereq in required:
            prereq_path.append({
                'paper_id': prereq['paper_id'],
                'title': prereq['title'],
                'reason': 'Required prerequisite',
                'time': prereq.get('implementation_time_hours', 'unknown')
            })

        return {
            'found': True,
            'recommendation': 'not_yet',
            'message': f"Not yet - implement prerequisites first",
            'reasoning': {
                'paper': paper['title'],
                'difficulty': paper['difficulty'],
                'missing_prerequisites': len(required),
                'why_wait': f"This paper builds on concepts from {len(required)} papers you haven't implemented yet.",
            },
            'suggested_path': prereq_path,
            'next_steps': f"Start with '{required[0]['title']}' - it's a required prerequisite.",
        }

    def _build_difficulty_warning(self, paper: Dict, expertise: str) -> Dict:
        """Build difficulty warning response"""

        difficulty_map = {'beginner': 1, 'intermediate': 2, 'advanced': 3}
        paper_level = difficulty_map.get(paper['difficulty'], 2)
        user_level = difficulty_map.get(expertise, 2)

        if paper_level > user_level + 1:
            return {
                'found': True,
                'recommendation': 'too_difficult',
                'message': f"This might be too challenging right now",
                'reasoning': {
                    'paper': paper['title'],
                    'paper_difficulty': paper['difficulty'],
                    'your_level': expertise,
                    'suggestion': 'Consider building up with intermediate papers first',
                },
            }

        return None  # No difficulty warning

    def _is_too_difficult(self, paper: Dict, expertise: str) -> bool:
        """Check if paper is too difficult for user's level"""
        difficulty_map = {'beginner': 1, 'intermediate': 2, 'advanced': 3}
        paper_level = difficulty_map.get(paper['difficulty'], 2)
        user_level = difficulty_map.get(expertise, 2)
        return paper_level > user_level + 1

    def _is_low_value(self, paper: Dict, user_context: Dict) -> bool:
        """Check if paper is low value for user's goals"""
        # For now, simple heuristic
        if paper.get('educational_value') == 'low':
            return True
        return False

    def _build_low_value_response(self, paper: Dict) -> Dict:
        """Build low value response"""
        return {
            'found': True,
            'recommendation': 'skip',
            'message': f"You can skip this one",
            'reasoning': {
                'paper': paper['title'],
                'why_skip': 'This paper has lower educational value. Better papers available for your time.',
            },
        }

    def _build_recommend_response(self, paper: Dict, recommended_prereqs: List[Dict],
                                  user_context: Dict) -> Dict:
        """Build positive recommendation response"""

        return {
            'found': True,
            'recommendation': 'yes',
            'message': f"Yes! This is worth implementing",
            'reasoning': {
                'paper': paper['title'],
                'difficulty': paper['difficulty'],
                'educational_value': paper['educational_value'],
                'production_relevance': paper['production_relevance'],
                'time_estimate': paper.get('implementation_time_hours', 'unknown'),
                'why_implement': paper.get('why_implement', ''),
            },
            'key_concepts': paper.get('key_concepts', []),
            'implementation_stages': self._suggest_stages(paper),
            'optional_prereqs': [p['title'] for p in recommended_prereqs] if recommended_prereqs else [],
        }

    def _suggest_stages(self, paper: Dict) -> List[str]:
        """Suggest implementation stages"""

        # Generic staged approach
        stages = [
            f"1. Read the paper and understand the core idea (2-3 hours)",
            f"2. Implement the minimal version (4-6 hours)",
            f"3. Test on small dataset and verify correctness (2-3 hours)",
            f"4. Scale up and compare with baselines (optional)",
        ]

        # Customize based on paper
        if 'dpo' in paper['paper_id'] or 'preference' in ' '.join(paper.get('key_concepts', [])):
            stages[1] = "2. Implement preference loss function (2-3 hours)"
            stages.insert(2, "3. Create preference dataset (2-3 hours)")

        return stages

    def get_learning_path(self, goal: str, expertise: str = 'intermediate') -> List[Dict]:
        """
        Generate a learning path for a specific goal

        Args:
            goal: e.g., "understand post-training", "implement DPO", "master RLHF"
            expertise: beginner/intermediate/advanced

        Returns:
            Ordered list of papers to implement
        """

        # For now, simple goal matching
        goal_lower = goal.lower()

        if 'dpo' in goal_lower or 'preference' in goal_lower:
            path_ids = ['sft_basics', 'reward_modeling', 'dpo_2023', 'orpo_2024']
        elif 'rlhf' in goal_lower:
            path_ids = ['sft_basics', 'reward_modeling', 'rlhf_instructgpt']
        elif 'post-training' in goal_lower or 'alignment' in goal_lower:
            path_ids = ['sft_basics', 'lima_2023', 'reward_modeling', 'dpo_2023', 'kto_2024']
        else:
            # Default path
            path_ids = ['sft_basics', 'dpo_2023']

        # Get full paper details
        path = []
        for paper_id in path_ids:
            paper = self.kb.get_paper(paper_id)
            if paper:
                path.append({
                    'paper_id': paper['paper_id'],
                    'title': paper['title'],
                    'difficulty': paper['difficulty'],
                    'time_estimate': paper.get('implementation_time_hours', 'unknown'),
                    'why': paper.get('why_implement', ''),
                })

        return path

    def close(self):
        """Clean up resources"""
        self.kb.close()
