#!/usr/bin/env python3
"""
Tutorial mode runner.
Orchestrates the file-based tutorial workflow.
"""

import os
import re
import sys
from typing import Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .skeleton import SkeletonGenerator
from .file_watcher import FileWatcher, TutorialSession


# Keywords that suggest user wants a full pipeline (not just core algorithm)
FULL_PIPELINE_KEYWORDS = [
    "full pipeline", "end-to-end", "from scratch", "complete training",
    "train .* from scratch", "full rlhf", "all stages", "entire",
    "data loader", "dataset preparation", "reproduce .* training",
]

# Topics that work well as single-file core algorithms
CORE_ALGORITHM_EXAMPLES = [
    "Loss functions: DPO, ORPO, KTO, contrastive loss, focal loss",
    "Architecture components: attention, patch embedding, layer norm",
    "Model classes: SimpleDPO, RewardModel, Transformer blocks",
    "Optimization: gradient clipping, learning rate schedulers",
]


class TutorialRunner:
    """
    Runs the file-based tutorial mode.

    Workflow:
    1. Generate complete implementation skeleton
    2. Write to file
    3. Watch file for changes
    4. Review TODOs as user completes them
    """

    def __init__(
        self,
        llm_client,
        paper_title: str = "",
        paper_context: str = "",
        console: Console = None,
    ):
        self.llm = llm_client
        self.paper_title = paper_title
        self.paper_context = paper_context
        self.console = console or Console()
        self.skeleton_generator = SkeletonGenerator(llm_client, paper_context)

    def extract_topic(self, query: str) -> str:
        """Extract the implementation topic from user query"""
        # Common patterns
        patterns = [
            r"implement\s+(.+)",
            r"learn\s+(?:about\s+)?(.+)",
            r"understand\s+(.+)",
            r"teach\s+(?:me\s+)?(.+)",
            r"tutorial\s+(?:on\s+|for\s+)?(.+)",
            r"how\s+(?:to\s+)?(?:implement\s+)?(.+)",
        ]

        query_lower = query.lower()

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                topic = match.group(1).strip()
                # Clean up common suffixes
                topic = re.sub(r'\s*(paper|algorithm|method|technique)$', '', topic)
                return topic.upper() if len(topic) <= 5 else topic.title()

        # If no pattern matches, use the whole query
        topic = query.strip()
        return topic.upper() if len(topic) <= 5 else topic.title()

    def _suggests_full_pipeline(self, query: str) -> bool:
        """Check if query suggests user wants a full pipeline"""
        query_lower = query.lower()
        for keyword in FULL_PIPELINE_KEYWORDS:
            if re.search(keyword, query_lower):
                return True
        return False

    def _prompt_scope_choice(self, topic: str) -> str:
        """
        Ask user to choose between core algorithm and full pipeline.

        Returns:
            'core' or 'pipeline'
        """
        self.console.print(Panel(
            f"[bold]What would you like to implement?[/bold]\n\n"
            f"[cyan](1) Core algorithm only[/cyan] [dim](recommended)[/dim]\n"
            f"    Single file focusing on the key contribution\n"
            f"    (loss function, architecture component, etc.)\n\n"
            f"[cyan](2) Full training pipeline[/cyan]\n"
            f"    Multi-file setup with data loading, training loop, etc.\n\n"
            f"[dim]Examples of core algorithms:[/dim]\n" +
            "\n".join(f"  - {ex}" for ex in CORE_ALGORITHM_EXAMPLES),
            title=f"Tutorial: {topic}",
            border_style="blue"
        ))

        choice = Prompt.ask(
            "Your choice",
            choices=["1", "2"],
            default="1"
        )

        return "core" if choice == "1" else "pipeline"

    def run(self, query: str, output_dir: str = ".", skip_choice: bool = False) -> bool:
        """
        Run the tutorial workflow.

        Args:
            query: User's query (e.g., "I want to implement DPO")
            output_dir: Directory to create the implementation file
            skip_choice: If True, skip the scope choice prompt (for testing)

        Returns:
            True if completed successfully, False otherwise
        """
        # Extract topic
        topic = self.extract_topic(query)

        # Check if query suggests full pipeline
        suggests_pipeline = self._suggests_full_pipeline(query)

        # Ask user to choose scope (unless skipped)
        if not skip_choice:
            scope = self._prompt_scope_choice(topic)

            if scope == "pipeline":
                self.console.print(Panel(
                    "[yellow]Full pipeline support is coming soon![/yellow]\n\n"
                    "For now, I'll help you with the [bold]core algorithm[/bold], "
                    "which is the heart of any implementation.\n\n"
                    "Once you've mastered the core, you can build the training "
                    "pipeline around it yourself - that's actually a great way to "
                    "solidify your understanding!",
                    title="Coming Soon",
                    border_style="yellow"
                ))
                self.console.print()

        self.console.print(Panel(
            f"[bold blue]Tutorial Mode[/bold blue]\n\n"
            f"Topic: [cyan]{topic}[/cyan] [dim](core algorithm)[/dim]\n\n"
            f"I'll generate an implementation skeleton with TODOs for you to complete.\n"
            f"Open the file in your IDE and fill in the TODOs - I'll review as you save.",
            title="Sherpa",
            border_style="blue"
        ))

        # Generate skeleton
        self.console.print("\n[dim]Generating implementation skeleton...[/dim]")

        try:
            filepath = self.skeleton_generator.write_to_file(topic, output_dir)
        except Exception as e:
            self.console.print(f"[red]Error generating skeleton: {e}[/red]")
            return False

        # Read the file to count TODOs
        with open(filepath, 'r') as f:
            code = f.read()
        total_todos = self.skeleton_generator.count_todos(code)

        # Success message
        filename = os.path.basename(filepath)
        self.console.print(f"\n[green]Created {filename}[/green]")
        self.console.print(f"[dim]Location: {os.path.abspath(filepath)}[/dim]")
        self.console.print(f"[dim]TODOs to complete: {total_todos}[/dim]")

        # Instructions
        self.console.print(Panel(
            f"[bold]Next Steps:[/bold]\n\n"
            f"1. Open [cyan]{filename}[/cyan] in your IDE (VS Code, Cursor, PyCharm, etc.)\n"
            f"2. Start with [yellow]TODO 1[/yellow] - read the goal and hint\n"
            f"3. Replace [dim]pass[/dim] with your implementation\n"
            f"4. Save the file - I'll automatically review your work\n\n"
            f"[dim]Tip: Take your time and think through each TODO before coding.[/dim]",
            title="Instructions",
            border_style="cyan"
        ))

        # Create session
        session = TutorialSession(
            filepath=filepath,
            topic=topic,
            total_todos=total_todos,
        )

        # Start file watcher
        watcher = FileWatcher(
            filepath=filepath,
            session=session,
            llm_client=self.llm,
            paper_context=self.paper_context,
            console=self.console,
        )

        self.console.print(f"\n[bold cyan]Waiting for you to complete TODO 1...[/bold cyan]")
        self.console.print("[dim]Press Ctrl+C to exit at any time.[/dim]\n")

        try:
            watcher.start()
            watcher.wait()
            return session.all_complete
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Tutorial interrupted.[/yellow]")
            self.console.print(f"[dim]Your progress is saved in {filename}[/dim]")
            self.console.print(f"[dim]Run 'sherpa --mode tutorial \"{query}\"' to resume.[/dim]")
            return False
        finally:
            watcher.stop()


def run_tutorial(
    query: str,
    llm_client,
    paper_title: str = "",
    paper_context: str = "",
    output_dir: str = ".",
    skip_choice: bool = False,
) -> bool:
    """
    Convenience function to run a tutorial.

    Args:
        query: User's query
        llm_client: LLM client for generation and review
        paper_title: Optional paper title for context
        paper_context: Optional paper context
        output_dir: Directory for output file
        skip_choice: If True, skip the scope choice prompt

    Returns:
        True if completed, False otherwise
    """
    runner = TutorialRunner(
        llm_client=llm_client,
        paper_title=paper_title,
        paper_context=paper_context,
    )
    return runner.run(query, output_dir, skip_choice=skip_choice)
