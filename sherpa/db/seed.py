#!/usr/bin/env python3
"""
Seed the knowledge base with curated post-training papers
"""

from .knowledge_base import KnowledgeBase


def seed_post_training_papers(db_path: str = None):
    """Seed the database with key post-training papers"""

    kb = KnowledgeBase(db_path)

    papers = [
        # Foundational papers
        {
            'paper_id': 'rlhf_instructgpt',
            'title': 'Training language models to follow instructions with human feedback (InstructGPT)',
            'arxiv_id': '2203.02155',
            'authors': 'Ouyang et al.',
            'year': 2022,
            'difficulty': 'intermediate',
            'educational_value': 'very_high',
            'production_relevance': 'very_high',
            'implementation_time_hours': '16-24',
            'key_concepts': ['rlhf', 'reward_modeling', 'ppo', 'human_feedback'],
            'description': 'The foundational RLHF paper from OpenAI. Introduces the three-stage process: SFT, reward model training, and RL fine-tuning.',
            'why_implement': 'Essential baseline for understanding all post-training techniques. Most production systems build on these ideas.',
            'github_repos': ['https://github.com/openai/following-instructions-human-feedback']
        },

        {
            'paper_id': 'dpo_2023',
            'title': 'Direct Preference Optimization: Your Language Model is Secretly a Reward Model',
            'arxiv_id': '2305.18290',
            'authors': 'Rafailov et al.',
            'year': 2023,
            'difficulty': 'intermediate',
            'educational_value': 'very_high',
            'production_relevance': 'very_high',
            'implementation_time_hours': '8-12',
            'key_concepts': ['preference_learning', 'implicit_reward', 'bradley_terry', 'rlhf_alternative'],
            'description': 'Simplifies RLHF by directly optimizing on preference data without an explicit reward model. Uses Bradley-Terry model.',
            'why_implement': 'Widely adopted alternative to RLHF. Simpler and more stable. Essential for modern post-training.',
            'github_repos': ['https://github.com/eric-mitchell/direct-preference-optimization']
        },

        # DPO variants and improvements
        {
            'paper_id': 'ipo_2023',
            'title': 'A General Theoretical Paradigm to Understand Learning from Human Preferences (IPO)',
            'arxiv_id': '2310.12036',
            'authors': 'Azar et al.',
            'year': 2023,
            'difficulty': 'advanced',
            'educational_value': 'high',
            'production_relevance': 'medium',
            'implementation_time_hours': '10-14',
            'key_concepts': ['preference_learning', 'ipo', 'theoretical_foundation'],
            'description': 'Provides theoretical foundation for preference learning and proposes IPO as an improvement over DPO.',
            'why_implement': 'Deepens understanding of why DPO works and when it might fail. Good for research-oriented implementations.',
        },

        {
            'paper_id': 'kto_2024',
            'title': 'KTO: Model Alignment as Prospect Theoretic Optimization',
            'arxiv_id': '2402.01306',
            'authors': 'Ethayarajh et al.',
            'year': 2024,
            'difficulty': 'intermediate',
            'educational_value': 'high',
            'production_relevance': 'high',
            'implementation_time_hours': '8-10',
            'key_concepts': ['kahneman_tversky', 'prospect_theory', 'binary_feedback'],
            'description': 'Uses Kahneman-Tversky human utility model. Works with simpler binary feedback instead of pairwise preferences.',
            'why_implement': 'Easier data collection (binary good/bad vs pairwise comparisons). Competitive performance with DPO.',
        },

        {
            'paper_id': 'orpo_2024',
            'title': 'ORPO: Monolithic Preference Optimization without Reference Model',
            'arxiv_id': '2403.07691',
            'authors': 'Hong et al.',
            'year': 2024,
            'difficulty': 'intermediate',
            'educational_value': 'medium',
            'production_relevance': 'medium',
            'implementation_time_hours': '6-8',
            'key_concepts': ['odds_ratio', 'reference_free', 'single_stage'],
            'description': 'Combines SFT and preference learning in one stage. Uses odds ratio instead of log probability ratio.',
            'why_implement': 'Simpler training pipeline (one stage vs two). Good for understanding DPO variations.',
        },

        # Supervised fine-tuning
        {
            'paper_id': 'sft_basics',
            'title': 'Supervised Fine-Tuning (Conceptual Foundation)',
            'arxiv_id': None,
            'authors': 'Multiple sources',
            'year': 2020,
            'difficulty': 'beginner',
            'educational_value': 'very_high',
            'production_relevance': 'very_high',
            'implementation_time_hours': '4-6',
            'key_concepts': ['supervised_learning', 'cross_entropy', 'instruction_tuning'],
            'description': 'Standard supervised fine-tuning on instruction-response pairs. Foundation for all post-training.',
            'why_implement': 'Absolute prerequisite. Must understand before moving to preference learning.',
        },

        # RLHF components
        {
            'paper_id': 'reward_modeling',
            'title': 'Learning to Summarize from Human Feedback (Reward Modeling)',
            'arxiv_id': '2009.01325',
            'authors': 'Stiennon et al.',
            'year': 2020,
            'difficulty': 'intermediate',
            'educational_value': 'high',
            'production_relevance': 'high',
            'implementation_time_hours': '8-10',
            'key_concepts': ['reward_model', 'pairwise_ranking', 'bradley_terry'],
            'description': 'Introduces reward modeling for summarization. Key component of RLHF pipeline.',
            'why_implement': 'Understanding reward models is crucial for both RLHF and understanding why DPO works.',
        },

        # Data quality and filtering
        {
            'paper_id': 'lima_2023',
            'title': 'LIMA: Less Is More for Alignment',
            'arxiv_id': '2305.11206',
            'authors': 'Zhou et al.',
            'year': 2023,
            'difficulty': 'beginner',
            'educational_value': 'high',
            'production_relevance': 'very_high',
            'implementation_time_hours': '4-6',
            'key_concepts': ['data_quality', 'instruction_tuning', 'alignment'],
            'description': 'Shows that 1000 carefully curated examples can achieve strong performance. Emphasizes data quality over quantity.',
            'why_implement': 'Changes perspective on data requirements. Quick to implement and very practical.',
        },

        # Recent advances
        {
            'paper_id': 'simpo_2024',
            'title': 'SimPO: Simple Preference Optimization with a Reference-Free Reward',
            'arxiv_id': '2405.14734',
            'authors': 'Meng et al.',
            'year': 2024,
            'difficulty': 'intermediate',
            'educational_value': 'medium',
            'production_relevance': 'medium',
            'implementation_time_hours': '6-8',
            'key_concepts': ['reference_free', 'length_normalization', 'target_reward_margin'],
            'description': 'Simplifies DPO by removing reference model and using length-normalized rewards.',
            'why_implement': 'Shows evolution of DPO ideas. Good for understanding what aspects of DPO are essential.',
        },

        {
            'paper_id': 'rso_2024',
            'title': 'Statistical Rejection Sampling Improves Preference Optimization (RSO)',
            'arxiv_id': '2309.06657',
            'authors': 'Liu et al.',
            'year': 2024,
            'difficulty': 'advanced',
            'educational_value': 'medium',
            'production_relevance': 'medium',
            'implementation_time_hours': '10-12',
            'key_concepts': ['rejection_sampling', 'statistical_advantages', 'iterative_optimization'],
            'description': 'Uses rejection sampling to improve preference data quality and optimization.',
            'why_implement': 'Advanced technique for those who have mastered DPO basics.',
        },
    ]

    # Add all papers
    print("Seeding knowledge base with post-training papers...")
    for paper in papers:
        if kb.add_paper(paper):
            print(f"  Added: {paper['title'][:60]}...")

    # Define prerequisite relationships
    prerequisites = [
        # DPO requires understanding SFT and reward modeling concepts
        ('dpo_2023', 'sft_basics', 'required'),
        ('dpo_2023', 'reward_modeling', 'recommended'),

        # RLHF requires SFT and reward modeling
        ('rlhf_instructgpt', 'sft_basics', 'required'),
        ('rlhf_instructgpt', 'reward_modeling', 'required'),

        # All DPO variants require DPO
        ('ipo_2023', 'dpo_2023', 'required'),
        ('kto_2024', 'dpo_2023', 'recommended'),
        ('orpo_2024', 'dpo_2023', 'recommended'),
        ('orpo_2024', 'sft_basics', 'required'),
        ('simpo_2024', 'dpo_2023', 'required'),
        ('rso_2024', 'dpo_2023', 'required'),

        # Reward modeling builds on SFT
        ('reward_modeling', 'sft_basics', 'recommended'),

        # LIMA is mostly independent but benefits from SFT understanding
        ('lima_2023', 'sft_basics', 'recommended'),
    ]

    print("\nAdding prerequisite relationships...")
    for paper_id, prereq_id, importance in prerequisites:
        kb.add_prerequisite(paper_id, prereq_id, importance)
        print(f"  {paper_id} -> {prereq_id} ({importance})")

    print(f"\nKnowledge base seeded successfully!")
    print(f"Total papers: {len(papers)}")

    kb.close()


if __name__ == "__main__":
    seed_post_training_papers()
