#!/usr/bin/env python3
"""
Simple ArXiv helper - works without full MCP SDK
"""

import arxiv
from typing import List, Dict


class ArxivHelper:
    """Simple wrapper around arxiv API"""

    def search_papers(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for papers on arXiv"""
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
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
