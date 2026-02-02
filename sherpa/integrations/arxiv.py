#!/usr/bin/env python3
"""
Simple ArXiv helper - works without full MCP SDK
"""

import arxiv
from typing import List, Dict, Optional


class ArxivHelper:
    """Simple wrapper around arxiv API"""

    def search_papers(
        self,
        query: str,
        max_results: int = 5,
        sort_by: str = "relevance",
        sort_order: str = "descending"
    ) -> List[Dict]:
        """Search for papers on arXiv

        Args:
            query: Search query
            max_results: Maximum number of results
            sort_by: "relevance", "submitted", or "updated"
            sort_order: "ascending" (oldest first) or "descending" (newest first)
        """
        sort_criterion = {
            "relevance": arxiv.SortCriterion.Relevance,
            "submitted": arxiv.SortCriterion.SubmittedDate,
            "updated": arxiv.SortCriterion.LastUpdatedDate,
        }.get(sort_by, arxiv.SortCriterion.Relevance)

        sort_order_enum = (
            arxiv.SortOrder.Ascending if sort_order == "ascending"
            else arxiv.SortOrder.Descending
        )

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_criterion,
            sort_order=sort_order_enum
        )

        results = []
        for paper in search.results():
            results.append({
                "arxiv_id": paper.entry_id.split('/')[-1],
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "abstract": paper.summary[:500] + "..." if len(paper.summary) > 500 else paper.summary,
                "published": paper.published.strftime("%Y-%m-%d"),
                "pdf_url": paper.pdf_url,
                "categories": paper.categories,
            })

        return results

    def search_foundational(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for foundational papers (oldest first by submission date)"""
        return self.search_papers(
            query=query,
            max_results=max_results,
            sort_by="submitted",
            sort_order="ascending"
        )

    def get_paper_by_id(self, arxiv_id: str) -> Dict:
        """Fetch a specific paper by arXiv ID"""
        arxiv_id = arxiv_id.replace("arxiv:", "")

        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(search.results())

        return {
            "arxiv_id": paper.entry_id.split('/')[-1],
            "title": paper.title,
            "authors": [author.name for author in paper.authors],
            "abstract": paper.summary,
            "published": paper.published.strftime("%Y-%m-%d"),
            "pdf_url": paper.pdf_url,
            "categories": paper.categories,
        }
