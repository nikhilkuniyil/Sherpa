#!/usr/bin/env python3
"""
Agentic Recommendation Engine
Uses Claude API to reason about paper recommendations and learning paths
"""

import os
import json
from typing import Dict, List, Optional
from anthropic import Anthropic
from ..db import KnowledgeBase
from ..integrations import ArxivHelper


class AgenticRecommendationEngine:
    """Uses Claude to make intelligent recommendations"""

    def __init__(self, api_key: Optional[str] = None):
        self.kb = KnowledgeBase()
        self.arxiv = ArxivHelper()

        # Initialize Anthropic client
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            print("Warning: No ANTHROPIC_API_KEY found. Agentic features disabled.")
            print("   Set with: export ANTHROPIC_API_KEY='your-key-here'")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.api_key)

    def get_learning_path_agentic(self, goal: str, user_context: Optional[Dict] = None) -> Dict:
        """
        Use Claude to generate a learning path based on goal

        Args:
            goal: User's learning goal (e.g., "understand DPO", "master post-training")
            user_context: Optional user context (implemented papers, expertise level)

        Returns:
            Dict with recommended path and reasoning
        """

        if not self.client:
            return {
                'error': 'Anthropic API key not configured',
                'fallback': 'Using basic recommendations'
            }

        # Get all papers from knowledge base
        all_papers = self.kb.get_all_papers()

        # Build context about available papers
        papers_context = self._build_papers_context(all_papers)

        # Build user context
        if user_context is None:
            user_context = {
                'implemented_papers': [],
                'expertise_level': 'intermediate'
            }

        # Create prompt for Claude
        prompt = self._build_learning_path_prompt(goal, papers_context, user_context)

        # Call Claude API
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            result = self._parse_learning_path_response(response.content[0].text)
            return result

        except Exception as e:
            return {
                'error': f'API call failed: {str(e)}',
                'fallback': 'Try basic recommendations instead'
            }

    def analyze_paper_agentic(self, paper_query: str, user_context: Optional[Dict] = None) -> Dict:
        """
        Use Claude to analyze if a paper is worth implementing

        This is more nuanced than rule-based - Claude can consider:
        - User's specific research goals
        - Current trends in the field
        - Practical vs theoretical value
        - Time investment vs learning ROI
        """

        if not self.client:
            return {
                'error': 'Anthropic API key not configured',
                'recommendation': 'unknown'
            }

        # Find the paper
        paper = self._find_paper(paper_query)
        if not paper:
            return {
                'found': False,
                'recommendation': 'unknown',
                'message': f"Paper '{paper_query}' not found in knowledge base."
            }

        # Get prerequisites
        prerequisites = self.kb.get_prerequisites(paper['paper_id'])

        # Build context
        paper_context = self._build_single_paper_context(paper, prerequisites)

        if user_context is None:
            user_context = {
                'implemented_papers': [],
                'expertise_level': 'intermediate'
            }

        # Create prompt
        prompt = self._build_recommendation_prompt(paper_context, user_context)

        # Call Claude
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            result = self._parse_recommendation_response(response.content[0].text, paper)
            return result

        except Exception as e:
            return {
                'error': f'API call failed: {str(e)}',
                'recommendation': 'unknown'
            }

    def _build_papers_context(self, papers: List[Dict]) -> str:
        """Build a context string describing all available papers"""

        context = "Available Papers in Knowledge Base:\n\n"

        for paper in papers:
            context += f"Paper ID: {paper['paper_id']}\n"
            context += f"Title: {paper['title']}\n"
            context += f"Difficulty: {paper['difficulty']}\n"
            context += f"Educational Value: {paper['educational_value']}\n"
            context += f"Time to Implement: {paper.get('implementation_time_hours', 'unknown')}\n"
            context += f"Key Concepts: {', '.join(paper.get('key_concepts', []))}\n"
            context += f"Why Implement: {paper.get('why_implement', 'N/A')}\n"

            # Add prerequisites
            prereqs = self.kb.get_prerequisites(paper['paper_id'])
            if prereqs:
                prereq_titles = [p['title'] for p in prereqs]
                context += f"Prerequisites: {', '.join(prereq_titles)}\n"

            context += "\n---\n\n"

        return context

    def _build_single_paper_context(self, paper: Dict, prerequisites: List[Dict]) -> str:
        """Build context for a single paper analysis"""

        context = f"""Paper to Analyze:
Title: {paper['title']}
Difficulty: {paper['difficulty']}
Educational Value: {paper['educational_value']}
Production Relevance: {paper['production_relevance']}
Time Estimate: {paper.get('implementation_time_hours', 'unknown')}
Key Concepts: {', '.join(paper.get('key_concepts', []))}
Description: {paper.get('description', 'N/A')}
Why Implement: {paper.get('why_implement', 'N/A')}

Prerequisites:
"""

        if prerequisites:
            for prereq in prerequisites:
                context += f"- {prereq['title']} ({prereq['importance']})\n"
        else:
            context += "None\n"

        return context

    def _build_learning_path_prompt(self, goal: str, papers_context: str, user_context: Dict) -> str:
        """Build prompt for learning path generation"""

        implemented = user_context.get('implemented_papers', [])
        expertise = user_context.get('expertise_level', 'intermediate')

        prompt = f"""You are an expert ML research advisor. A researcher wants to: "{goal}"

Their context:
- Expertise level: {expertise}
- Already implemented: {', '.join(implemented) if implemented else 'Nothing yet'}

{papers_context}

Based on this knowledge base, create an optimal learning path to achieve their goal.

Consider:
1. Prerequisites - ensure foundational papers come first
2. Difficulty progression - don't jump too quickly
3. Educational value - prioritize high-value papers
4. Goal alignment - papers should directly support their goal
5. Time investment - balance depth vs breadth

Return your response in this EXACT JSON format:
{{
  "path": [
    {{
      "paper_id": "paper_id_here",
      "reason": "Why this paper is important for the goal"
    }}
  ],
  "reasoning": "Overall explanation of the learning path strategy",
  "estimated_total_time": "X-Y hours",
  "key_milestones": ["After paper 1, you'll understand X", "After paper 3, you can Y"]
}}

Only include papers from the knowledge base. Order them from foundational to advanced.
"""

        return prompt

    def _build_recommendation_prompt(self, paper_context: str, user_context: Dict) -> str:
        """Build prompt for paper recommendation"""

        implemented = user_context.get('implemented_papers', [])
        expertise = user_context.get('expertise_level', 'intermediate')
        goal = user_context.get('research_goal', 'understanding post-training techniques')

        prompt = f"""You are an expert ML research advisor. A researcher is considering implementing a paper.

Researcher's context:
- Expertise level: {expertise}
- Research goal: {goal}
- Already implemented: {', '.join(implemented) if implemented else 'Nothing yet'}

{paper_context}

Should they implement this paper right now? Provide your recommendation.

Return your response in this EXACT JSON format:
{{
  "recommendation": "yes|not_yet|skip|too_difficult",
  "confidence": "high|medium|low",
  "reasoning": "Detailed explanation of your recommendation",
  "next_steps": "What they should do (implement now, do X first, etc.)",
  "time_to_implement": "X-Y hours estimate",
  "key_takeaways": ["What they'll learn from implementing this"]
}}

Be honest and practical. If prerequisites are missing, say "not_yet". If the paper isn't valuable for their goal, say "skip".
"""

        return prompt

    def _parse_learning_path_response(self, response_text: str) -> Dict:
        """Parse Claude's learning path response"""

        try:
            # Extract JSON from response
            # Claude might wrap it in ```json``` blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            result = json.loads(json_text)

            # Enrich with full paper details
            enriched_path = []
            for item in result.get('path', []):
                paper = self.kb.get_paper(item['paper_id'])
                if paper:
                    enriched_path.append({
                        'paper_id': paper['paper_id'],
                        'title': paper['title'],
                        'difficulty': paper['difficulty'],
                        'time_estimate': paper.get('implementation_time_hours', 'unknown'),
                        'reason': item.get('reason', ''),
                    })

            result['path'] = enriched_path
            return result

        except Exception as e:
            return {
                'error': f'Failed to parse response: {str(e)}',
                'raw_response': response_text
            }

    def _parse_recommendation_response(self, response_text: str, paper: Dict) -> Dict:
        """Parse Claude's recommendation response"""

        try:
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            result = json.loads(json_text)

            # Add paper info
            result['found'] = True
            result['paper'] = paper['title']

            return result

        except Exception as e:
            return {
                'error': f'Failed to parse response: {str(e)}',
                'raw_response': response_text,
                'found': True,
                'paper': paper['title']
            }

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

    def close(self):
        """Clean up resources"""
        self.kb.close()
