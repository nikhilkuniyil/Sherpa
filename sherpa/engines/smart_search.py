#!/usr/bin/env python3
"""
Smart paper search with intent classification and progressive disclosure.
"""

import json
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from ..integrations import ArxivHelper

if TYPE_CHECKING:
    from ..llm import UnifiedLLMClient


@dataclass
class SearchState:
    """Tracks what has been shown in the current session"""
    query: str = ""
    intent: str = ""  # "understand", "latest", "implement"
    shown_papers: List[str] = field(default_factory=list)  # arxiv_ids already shown
    all_results: List[Dict] = field(default_factory=list)  # full ranked results
    current_batch: int = 0
    has_more: bool = False


class SmartSearchEngine:
    """
    Intelligent paper search with:
    - Intent classification (understand/latest/implement)
    - Relevance filtering (removes off-topic results)
    - Practical ordering (not just chronological)
    - Progressive disclosure (2-3 papers at a time)
    """

    BATCH_SIZE = 3

    def __init__(self, claude_client: Optional['UnifiedLLMClient'] = None, kb=None):
        self.claude = claude_client
        self.kb = kb
        self.arxiv = ArxivHelper()
        self.state = SearchState()

    def search(self, query: str, force_intent: str = None) -> Dict:
        """
        Main search entry point.

        Returns:
            {
                "intent": str,
                "papers": List[Dict],  # Current batch
                "has_more": bool,
                "follow_up_prompt": str,
                "background_reading": List[Dict],  # For "latest" intent
                "prerequisites": List[Dict],  # For "implement" intent
            }
        """
        if not self.claude:
            # Fallback to basic search without Claude
            results = self.arxiv.search_papers(query, max_results=10)
            return {
                "intent": "unknown",
                "papers": results[:self.BATCH_SIZE],
                "has_more": len(results) > self.BATCH_SIZE,
                "follow_up_prompt": "Use 'more' to see additional papers.",
            }

        # Reset state for new query
        self.state = SearchState(query=query)

        # Step 1: Classify intent
        intent = force_intent or self._classify_intent(query)
        self.state.intent = intent

        # Step 2: Fetch candidates from arXiv
        candidates = self._fetch_candidates(query, intent)

        # Step 3: Filter and rank with Claude
        ranked_papers = self._filter_and_rank(query, intent, candidates)
        self.state.all_results = ranked_papers

        # Step 4: Return first batch with progressive disclosure
        return self._get_batch_response(intent)

    def get_more(self) -> Dict:
        """Get next batch of papers"""
        if not self.state.all_results:
            return {"error": "No active search. Run a search first."}

        self.state.current_batch += 1
        return self._get_batch_response(self.state.intent)

    def _classify_intent(self, query: str) -> str:
        """Use Claude to classify the user's intent"""
        prompt = f"""Classify the user's intent for this ML paper search query.

Query: "{query}"

Intent categories:
- "understand": User wants to learn a concept from scratch (signals: "learn", "understand", "explain", "what is", "how does", "introduction", "basics", topic names without qualifiers)
- "latest": User wants recent developments (signals: "latest", "new", "recent", "2024", "2025", "state-of-the-art", "improvements", "advances")
- "implement": User wants to implement something specific (signals: "implement", "code", "build", "should I implement", "how to implement")

If ambiguous between "understand" and another intent, default to "understand".

Respond with ONLY the intent word: "understand", "latest", or "implement"."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            intent = response.content[0].text.strip().lower()
            if intent in ["understand", "latest", "implement"]:
                return intent
            return "understand"  # default
        except Exception:
            return "understand"

    def _fetch_candidates(self, query: str, intent: str) -> List[Dict]:
        """Fetch candidate papers from arXiv based on intent"""
        candidates = []
        seen_ids = set()

        # Primary search
        primary = self.arxiv.search_papers(query, max_results=15)
        for p in primary:
            if p['arxiv_id'] not in seen_ids:
                candidates.append(p)
                seen_ids.add(p['arxiv_id'])

        # For "understand" intent, also search oldest-first
        if intent == "understand":
            oldest = self.arxiv.search_foundational(query, max_results=10)
            for p in oldest:
                if p['arxiv_id'] not in seen_ids:
                    candidates.append(p)
                    seen_ids.add(p['arxiv_id'])

        return candidates

    def _filter_and_rank(self, query: str, intent: str, candidates: List[Dict]) -> List[Dict]:
        """Use Claude to filter irrelevant papers and rank by practical value"""
        if not candidates:
            return []

        # Build candidate summary for Claude
        candidate_summary = "\n".join([
            f"{i+1}. [{p['arxiv_id']}] {p['title']} ({p['published'][:4]})\n   Abstract: {p['abstract'][:200]}..."
            for i, p in enumerate(candidates[:20])
        ])

        prompt = f"""You are helping a researcher find ML papers. Filter and rank these arXiv results.

USER QUERY: "{query}"
USER INTENT: {intent}

CANDIDATE PAPERS:
{candidate_summary}

TASK:
1. FILTER: Remove papers that are NOT relevant to the query. Be strict - if a paper is about a completely different topic (e.g., physics experiments when searching for ML), exclude it.

2. RANK based on intent:
   - "understand": Rank by PRACTICAL educational value. The best entry points for learning, not necessarily the oldest. Consider: clarity, influence, prerequisite knowledge needed. A well-written tutorial paper may be better than a dense theoretical one.
   - "latest": Rank by recency and impact. Most recent high-quality work first.
   - "implement": Put the specific requested paper first, then its prerequisites.

3. CATEGORIZE each paper as:
   - "foundational": Seminal work that introduced key concepts
   - "practical": Good for hands-on implementation
   - "recent": Latest developments/improvements
   - "dense": Important but difficult to read

Respond in JSON:
{{
  "ranked_papers": [
    {{
      "arxiv_id": "...",
      "category": "foundational|practical|recent|dense",
      "relevance_score": 1-10,
      "why": "brief reason for ranking/inclusion"
    }},
    ...
  ],
  "excluded": ["arxiv_id1", "arxiv_id2"],  // papers filtered out as irrelevant
  "notes": "any observations about the results"
}}

Only include papers with relevance_score >= 6."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            ranking = json.loads(response_text)

            # Build final list with metadata
            id_to_paper = {p['arxiv_id']: p for p in candidates}
            ranked = []

            for item in ranking.get('ranked_papers', []):
                arxiv_id = item.get('arxiv_id', '')
                if arxiv_id in id_to_paper:
                    paper = id_to_paper[arxiv_id].copy()
                    paper['_category'] = item.get('category', '')
                    paper['_relevance'] = item.get('relevance_score', 5)
                    paper['_why'] = item.get('why', '')
                    ranked.append(paper)

            return ranked

        except Exception as e:
            # Fallback: return candidates as-is
            return candidates[:10]

    def _get_batch_response(self, intent: str) -> Dict:
        """Get the current batch of papers with appropriate framing"""
        all_papers = self.state.all_results
        start_idx = self.state.current_batch * self.BATCH_SIZE
        end_idx = start_idx + self.BATCH_SIZE

        batch = all_papers[start_idx:end_idx]
        remaining = all_papers[end_idx:]

        # Track shown papers
        for p in batch:
            if p['arxiv_id'] not in self.state.shown_papers:
                self.state.shown_papers.append(p['arxiv_id'])

        self.state.has_more = len(remaining) > 0

        # Build response based on intent
        result = {
            "intent": intent,
            "papers": batch,
            "has_more": self.state.has_more,
        }

        # Add follow-up prompts
        if self.state.has_more:
            if intent == "understand":
                if self.state.current_batch == 0:
                    result["follow_up_prompt"] = "Want to see more papers in this space? Type 'more'"
                else:
                    result["follow_up_prompt"] = "Ready to explore the latest work? Type 'more'"
            elif intent == "latest":
                result["follow_up_prompt"] = "Want to see more recent papers? Type 'more'"
            else:
                result["follow_up_prompt"] = "Need more options? Type 'more'"

        # For "latest" intent, add foundational papers as background
        if intent == "latest" and self.state.current_batch == 0:
            foundational = [p for p in all_papers if p.get('_category') == 'foundational']
            if foundational:
                result["background_reading"] = foundational[:2]

        # For "implement" intent, identify prerequisites
        if intent == "implement" and self.state.current_batch == 0:
            prereqs = [p for p in all_papers[1:] if p.get('_category') in ['foundational', 'practical']]
            if prereqs:
                result["prerequisites"] = prereqs[:3]

        return result

    def get_paper_recommendation(self, query: str, user_completed: List[str] = None) -> Dict:
        """
        Get a paper recommendation with prerequisite checking.

        Args:
            query: What the user wants to implement/learn
            user_completed: List of paper_ids the user has already completed
        """
        user_completed = user_completed or []

        # First, search for papers
        search_result = self.search(query, force_intent="implement")

        if not search_result.get('papers'):
            return {"error": "No relevant papers found."}

        target_paper = search_result['papers'][0]
        prereqs = search_result.get('prerequisites', [])

        # Check which prerequisites are missing
        missing_prereqs = []
        for p in prereqs:
            paper_id = p.get('arxiv_id', '')
            # Check against both arxiv_id and any paper_id in KB
            if paper_id not in user_completed:
                missing_prereqs.append(p)

        result = {
            "target_paper": target_paper,
            "prerequisites": prereqs,
            "missing_prerequisites": missing_prereqs,
        }

        if missing_prereqs:
            result["recommendation"] = "not_yet"
            result["message"] = f"Before implementing this, consider these foundational papers:"
        else:
            result["recommendation"] = "ready"
            result["message"] = "You're ready to implement this paper!"

        return result
