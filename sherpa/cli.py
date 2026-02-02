#!/usr/bin/env python3
"""
Sherpa - Paper Implementation Coach CLI

Usage:
    sherpa "Should I implement DPO?"
    sherpa --path "learn DPO"
    sherpa --list
    sherpa --agentic --path "learn DPO"  # Use Claude for reasoning
"""

import sys
import os
import argparse
from typing import Dict

from .engines import RecommendationEngine, AgenticRecommendationEngine
from .db import KnowledgeBase


class Sherpa:
    """Main CLI interface for Sherpa"""

    def __init__(self, use_agentic=False):
        self.kb = KnowledgeBase()

        # Try to use agentic engine if requested or if API key available
        self.agentic_available = os.getenv('ANTHROPIC_API_KEY') is not None

        if use_agentic or self.agentic_available:
            self.agentic_engine = AgenticRecommendationEngine()
            if self.agentic_engine.client:
                self.use_agentic = True
                print("Using Agentic Mode (Claude-powered reasoning)")
            else:
                self.use_agentic = False
                self.engine = RecommendationEngine()
                print("Using Rule-based Mode (set ANTHROPIC_API_KEY for agentic mode)")
        else:
            self.use_agentic = False
            self.engine = RecommendationEngine()
            print("Using Rule-based Mode (use --agentic flag for Claude-powered reasoning)")

    def ask(self, question: str, context: dict = None):
        """Ask the coach about a paper"""

        # Parse the question to extract paper name
        paper_query = self._extract_paper_query(question)

        if not paper_query:
            print("\nI'm not sure which paper you're asking about.")
            print("Try: 'Should I implement DPO?' or 'Is ORPO worth implementing?'")
            return

        # Get recommendation
        result = self.engine.analyze_paper(paper_query, context)

        # Display result
        self._display_recommendation(result)

    def _extract_paper_query(self, question: str) -> str:
        """Extract paper name from natural language question"""

        # Common patterns
        question_lower = question.lower()

        # Map common queries to paper IDs
        # This handles acronyms and common names
        query_map = {
            'dpo': 'dpo_2023',
            'direct preference optimization': 'dpo_2023',
            'orpo': 'orpo_2024',
            'kto': 'kto_2024',
            'ipo': 'ipo_2023',
            'rlhf': 'rlhf_instructgpt',
            'instructgpt': 'rlhf_instructgpt',
            'lima': 'lima_2023',
            'simpo': 'simpo_2024',
            'rso': 'rso_2024',
            'sft': 'sft_basics',
            'supervised fine-tuning': 'sft_basics',
            'reward model': 'reward_modeling',
        }

        # Check for direct matches
        for query, paper_id in query_map.items():
            if query in question_lower:
                return paper_id

        # Try partial title match
        known_papers = self.kb.get_all_papers()
        for paper in known_papers:
            title_lower = paper['title'].lower()
            # Check if significant words from title appear in question
            title_words = set(title_lower.split())
            question_words = set(question_lower.split())

            # If 3+ words match, it's probably this paper
            common_words = title_words & question_words
            if len(common_words) >= 3:
                return paper['paper_id']

        # If no match, return the question as-is and let the engine handle it
        return question

    def _display_recommendation(self, result: dict):
        """Display recommendation in a nice format"""

        if not result['found']:
            print(f"\n{result['message']}\n")
            return

        rec = result['recommendation']

        # Header
        print("\n" + "=" * 70)

        if rec == 'yes':
            print("YES - This is worth implementing!")
        elif rec == 'not_yet':
            print("NOT YET - Prerequisites first")
        elif rec == 'too_difficult':
            print("CHALLENGING - Might be too advanced")
        elif rec == 'skip':
            print("SKIP - Better options available")
        else:
            print(f"{result['message']}")

        print("=" * 70)

        # Reasoning
        if 'reasoning' in result:
            reasoning = result['reasoning']
            print(f"\nPaper: {reasoning.get('paper', 'Unknown')}")

            if 'difficulty' in reasoning:
                print(f"Difficulty: {reasoning['difficulty']}")

            if 'educational_value' in reasoning:
                print(f"Educational Value: {reasoning['educational_value']}")

            if 'production_relevance' in reasoning:
                print(f"Production Relevance: {reasoning['production_relevance']}")

            if 'time_estimate' in reasoning:
                print(f"Time Estimate: {reasoning['time_estimate']} hours")

            if 'why_implement' in reasoning and reasoning['why_implement']:
                print(f"\nWhy implement:")
                print(f"   {reasoning['why_implement']}")

        # Key concepts
        if 'key_concepts' in result and result['key_concepts']:
            print(f"\nKey Concepts:")
            for concept in result['key_concepts']:
                print(f"   - {concept.replace('_', ' ').title()}")

        # Prerequisites
        if 'suggested_path' in result:
            print(f"\nRecommended Path:")
            for i, prereq in enumerate(result['suggested_path'], 1):
                print(f"   {i}. {prereq['title'][:55]}...")
                print(f"      ({prereq['time']} hours - {prereq['reason']})")

            if 'next_steps' in result:
                print(f"\n{result['next_steps']}")

        # Implementation stages
        if 'implementation_stages' in result:
            print(f"\nSuggested Implementation Stages:")
            for stage in result['implementation_stages']:
                print(f"   {stage}")

        # Optional prerequisites
        if 'optional_prereqs' in result and result['optional_prereqs']:
            print(f"\nOptional (but helpful) prerequisites:")
            for prereq in result['optional_prereqs']:
                print(f"   - {prereq}")

        print("\n")

    def show_learning_path(self, goal: str, expertise: str = 'intermediate'):
        """Show a complete learning path"""

        if self.use_agentic:
            # Use Claude to generate path
            user_context = {
                'expertise_level': expertise,
                'implemented_papers': [],  # TODO: Track this
                'research_goal': goal
            }

            result = self.agentic_engine.get_learning_path_agentic(goal, user_context)

            if 'error' in result:
                print(f"\nError: {result['error']}")
                print("Falling back to rule-based recommendations...")
                path = self.engine.get_learning_path(goal, expertise)
            else:
                self._display_agentic_path(result, goal)
                return
        else:
            path = self.engine.get_learning_path(goal, expertise)

        # Display rule-based path
        print("\n" + "=" * 70)
        print(f"Learning Path: {goal}")
        print("=" * 70)

        total_time_min = 0
        total_time_max = 0

        for i, paper in enumerate(path, 1):
            print(f"\n{i}. {paper['title']}")
            print(f"   Difficulty: {paper['difficulty']}")
            print(f"   Time: {paper['time_estimate']} hours")

            if paper.get('why'):
                print(f"   {paper['why'][:70]}...")

            # Parse time estimate
            time_str = paper['time_estimate']
            if '-' in time_str:
                parts = time_str.split('-')
                try:
                    total_time_min += int(parts[0])
                    total_time_max += int(parts[1])
                except:
                    pass

        print(f"\n{'-' * 70}")
        if total_time_min > 0:
            print(f"Total Estimated Time: {total_time_min}-{total_time_max} hours")
            print(f"   (~{total_time_min // 8}-{total_time_max // 8} days of focused work)")
        print()

    def _display_agentic_path(self, result: Dict, goal: str):
        """Display agentic learning path results"""

        print("\n" + "=" * 70)
        print(f"AI-Generated Learning Path: {goal}")
        print("=" * 70)

        # Show reasoning
        if 'reasoning' in result:
            print(f"\nStrategy:")
            print(f"   {result['reasoning']}\n")

        # Show path
        path = result.get('path', [])
        for i, paper in enumerate(path, 1):
            print(f"\n{i}. {paper['title']}")
            print(f"   Difficulty: {paper['difficulty']}")
            print(f"   Time: {paper['time_estimate']} hours")
            print(f"   Why: {paper.get('reason', 'N/A')}")

        # Show milestones
        if 'key_milestones' in result and result['key_milestones']:
            print(f"\nKey Milestones:")
            for milestone in result['key_milestones']:
                print(f"   - {milestone}")

        # Show total time
        print(f"\n{'-' * 70}")
        if 'estimated_total_time' in result:
            print(f"Total Estimated Time: {result['estimated_total_time']}")
        print()

    def list_papers(self, domain: str = 'post-training'):
        """List all papers in a domain"""

        papers = self.kb.search_papers(domain=domain)

        print(f"\nAvailable Papers in '{domain}':")
        print("=" * 70)

        # Group by difficulty
        by_difficulty = {'beginner': [], 'intermediate': [], 'advanced': []}
        for paper in papers:
            diff = paper.get('difficulty', 'intermediate')
            by_difficulty[diff].append(paper)

        for difficulty in ['beginner', 'intermediate', 'advanced']:
            if by_difficulty[difficulty]:
                print(f"\n{difficulty.upper()} ({len(by_difficulty[difficulty])} papers)")
                print("-" * 70)

                for paper in by_difficulty[difficulty]:
                    print(f"\n  - {paper['title'][:60]}...")
                    print(f"    ID: {paper['paper_id']}")
                    if paper.get('arxiv_id'):
                        print(f"    ArXiv: {paper['arxiv_id']}")
                    print(f"    Value: {paper.get('educational_value', 'unknown')}")

        print()

    def close(self):
        """Clean up"""
        if self.use_agentic:
            self.agentic_engine.close()
        else:
            self.engine.close()
        self.kb.close()


def main():
    """Main CLI entry point"""

    parser = argparse.ArgumentParser(
        description='Sherpa - Your guide to implementing ML papers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sherpa "Should I implement DPO?"
  sherpa --path "learn DPO"
  sherpa --list
  sherpa -i                              # Start interactive implementation mode
  sherpa --implement dpo_2023            # Start implementing a specific paper
        """
    )

    parser.add_argument('question', nargs='?', help='Question about a paper')
    parser.add_argument('--path', help='Get learning path for a goal')
    parser.add_argument('--list', action='store_true', help='List all available papers')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Start interactive implementation REPL')
    parser.add_argument('--implement', metavar='PAPER',
                        help='Start implementing a specific paper')
    parser.add_argument('--agentic', action='store_true',
                        help='Use Claude API for intelligent reasoning (requires ANTHROPIC_API_KEY)')
    parser.add_argument('--expertise', default='intermediate',
                        choices=['beginner', 'intermediate', 'advanced'],
                        help='Your expertise level')

    args = parser.parse_args()

    # Interactive mode
    if args.interactive or args.implement:
        from .repl import ImplementationREPL
        repl = ImplementationREPL()
        if args.implement:
            # Pre-load the specified paper
            repl._cmd_load(args.implement)
        repl.run()
        return

    guide = Sherpa(use_agentic=args.agentic)

    try:
        if args.list:
            guide.list_papers()
        elif args.path:
            guide.show_learning_path(args.path, args.expertise)
        elif args.question:
            # For now, assume no prerequisites implemented
            # Later we can track this in a config file
            context = {
                'implemented_papers': [],
                'expertise_level': args.expertise
            }
            guide.ask(args.question, context)
        else:
            parser.print_help()

    finally:
        guide.close()


if __name__ == "__main__":
    main()
