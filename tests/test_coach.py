#!/usr/bin/env python3
"""
Test suite for Paper Implementation Coach
"""

import pytest
import tempfile
import os

from paper_coach.db import KnowledgeBase
from paper_coach.db.seed import seed_post_training_papers
from paper_coach.engines import RecommendationEngine


class TestKnowledgeBase:
    """Tests for the knowledge base"""

    def test_create_database(self, tmp_path):
        """Test database creation"""
        db_path = str(tmp_path / "test.db")
        kb = KnowledgeBase(db_path)

        assert os.path.exists(db_path)
        kb.close()

    def test_add_and_retrieve_paper(self, tmp_path):
        """Test adding and retrieving a paper"""
        db_path = str(tmp_path / "test.db")
        kb = KnowledgeBase(db_path)

        paper = {
            'paper_id': 'test_paper',
            'title': 'Test Paper Title',
            'difficulty': 'intermediate',
            'educational_value': 'high',
        }

        kb.add_paper(paper)
        retrieved = kb.get_paper('test_paper')

        assert retrieved is not None
        assert retrieved['title'] == 'Test Paper Title'
        kb.close()


class TestRecommendationEngine:
    """Tests for the recommendation engine"""

    def test_analyze_unknown_paper(self):
        """Test analyzing a paper not in the database"""
        engine = RecommendationEngine()

        result = engine.analyze_paper("nonexistent_paper_xyz")

        assert result['found'] == False
        assert result['recommendation'] == 'unknown'
        engine.close()


def run_all_tests():
    """Run all tests manually"""
    print("\n" + "=" * 70)
    print("Paper Implementation Coach - Test Suite")
    print("=" * 70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Knowledge Base
    print("\n[1/4] Testing Knowledge Base...")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")
            kb = KnowledgeBase(db_path)
            assert os.path.exists(db_path), "Database file not created"
            kb.close()
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 2: Seed Database
    print("\n[2/4] Testing Database Seeding...")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.db")
            seed_post_training_papers(db_path)
            kb = KnowledgeBase(db_path)
            papers = kb.get_all_papers()
            assert len(papers) >= 10, f"Expected at least 10 papers, got {len(papers)}"
            kb.close()
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 3: Recommendation Engine - Unknown Paper
    print("\n[3/4] Testing Recommendation Engine (unknown paper)...")
    try:
        engine = RecommendationEngine()
        result = engine.analyze_paper("nonexistent_paper_xyz")
        assert result['found'] == False
        assert result['recommendation'] == 'unknown'
        engine.close()
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 4: Recommendation Engine - Known Paper
    print("\n[4/4] Testing Recommendation Engine (known paper)...")
    try:
        engine = RecommendationEngine()
        result = engine.analyze_paper("dpo_2023")
        assert result['found'] == True
        assert result['recommendation'] in ['yes', 'not_yet', 'skip', 'too_difficult']
        engine.close()
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTests Passed: {tests_passed}/{tests_passed + tests_failed}")

    if tests_failed == 0:
        print("\nAll tests passed!")
        return 0
    else:
        print(f"\n{tests_failed} test(s) failed.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
