#!/usr/bin/env python3
"""
Test suite for ArXiv helper
"""

import pytest
from paper_coach.integrations import ArxivHelper


def test_arxiv_search():
    """Test basic arxiv search functionality"""
    helper = ArxivHelper()

    papers = helper.search_papers("Direct Preference Optimization", max_results=2)

    assert len(papers) > 0
    assert 'title' in papers[0]
    assert 'arxiv_id' in papers[0]
    assert 'authors' in papers[0]


def test_arxiv_get_by_id():
    """Test fetching paper by arxiv ID"""
    helper = ArxivHelper()

    # DPO paper ID
    paper = helper.get_paper_by_id("2305.18290")

    assert paper is not None
    assert 'title' in paper
    assert 'Direct Preference Optimization' in paper['title']


if __name__ == "__main__":
    print("Testing ArXiv Helper...")
    print("-" * 50)

    helper = ArxivHelper()

    try:
        print("\nSearching for 'Direct Preference Optimization'...")
        papers = helper.search_papers("Direct Preference Optimization", max_results=2)

        print(f"Found {len(papers)} papers")

        if papers:
            print(f"\nFirst result:")
            print(f"  Title: {papers[0]['title'][:80]}...")
            print(f"  ArXiv ID: {papers[0]['arxiv_id']}")
            print(f"  Authors: {', '.join(papers[0]['authors'][:3])}")
            print(f"  Published: {papers[0]['published']}")

            print(f"\nFetching paper by ID: {papers[0]['arxiv_id']}...")
            paper = helper.get_paper_by_id(papers[0]['arxiv_id'])
            print(f"Retrieved: {paper['title'][:60]}...")

        print("\n" + "=" * 50)
        print("All tests passed! ArXiv helper is working.")

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
