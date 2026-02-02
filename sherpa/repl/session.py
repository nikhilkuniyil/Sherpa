#!/usr/bin/env python3
"""
Interactive REPL session for implementation coaching.
"""

import os
import sys
from typing import Optional, Dict, List
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from anthropic import Anthropic

from ..db import KnowledgeBase, SessionManager, ImplementationSession
from ..pdf import PDFParser, ParsedPaper
from ..integrations import ClaudeCodeInterface, check_claude_code_available, ArxivHelper
from ..config import get_api_key
from .commands import get_command_help, COMMANDS


class ImplementationREPL:
    """Interactive REPL for paper implementation coaching"""

    def __init__(self):
        self.console = Console()
        self.kb = KnowledgeBase()
        self.session_manager = SessionManager(self.kb)
        self.pdf_parser = PDFParser()
        self.arxiv = ArxivHelper()

        # Current state
        self.current_paper: Optional[Dict] = None
        self.parsed_content: Optional[ParsedPaper] = None
        self.current_session: Optional[ImplementationSession] = None
        self.claude_code: Optional[ClaudeCodeInterface] = None

        # Claude API for explanations - use config system
        api_key = get_api_key(prompt_if_missing=True)
        self.claude = Anthropic(api_key=api_key) if api_key else None

        # REPL setup
        history_path = Path.home() / '.sherpa' / 'repl_history'
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.prompt_session = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
        )

    def run(self):
        """Main REPL loop"""
        self._print_welcome()

        while True:
            try:
                prompt = self._get_prompt()
                user_input = self.prompt_session.prompt(prompt)

                if not user_input.strip():
                    continue

                result = self._process_command(user_input.strip())

                if result == 'exit':
                    self._handle_exit()
                    break

            except KeyboardInterrupt:
                self.console.print("\n[dim]Use 'exit' to quit[/dim]")
            except EOFError:
                self._handle_exit()
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def _print_welcome(self):
        """Print welcome message"""
        welcome = """
[bold blue]Sherpa[/bold blue] - Paper Implementation Coach

Your guide to implementing ML papers step by step.

[dim]Commands: load, fetch, start, explain, implement, help
Type 'help' for all commands or 'help <cmd>' for details.[/dim]
"""
        self.console.print(Panel(welcome, border_style="blue"))

        if self.claude:
            self.console.print("[green]Claude API connected.[/green]")
        else:
            self.console.print("[yellow]Note: No API key configured. Run 'sherpa --setup' or set ANTHROPIC_API_KEY.[/yellow]")

        if not check_claude_code_available():
            self.console.print("[dim]Note: Claude Code CLI not found. 'implement' command unavailable.[/dim]")

    def _get_prompt(self) -> str:
        """Generate context-aware prompt"""
        parts = ['sherpa']

        if self.current_paper:
            parts.append(f"[{self.current_paper['paper_id']}]")

        if self.current_session:
            stage = self.current_session.current_stage
            if self.current_session.stages:
                stage_name = self.current_session.stages[stage].get('stage_name', f's{stage}')
                parts.append(f"({stage_name})")

        return ' '.join(parts) + '> '

    def _process_command(self, user_input: str) -> Optional[str]:
        """Process user input and dispatch to handlers"""
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        handlers = {
            'load': self._cmd_load,
            'fetch': self._cmd_fetch,
            'start': self._cmd_start,
            'resume': self._cmd_resume,
            'sessions': self._cmd_sessions,
            'status': self._cmd_status,
            'explain': self._cmd_explain,
            'equation': self._cmd_equation,
            'algorithm': self._cmd_algorithm,
            'ask': self._cmd_ask,
            'summary': self._cmd_summary,
            'plan': self._cmd_plan,
            'stage': self._cmd_stage,
            'implement': self._cmd_implement,
            'code': self._cmd_code,
            'files': self._cmd_files,
            'done': self._cmd_done,
            'skip': self._cmd_skip,
            'note': self._cmd_note,
            'progress': self._cmd_progress,
            'help': self._cmd_help,
            'papers': self._cmd_papers,
            'search': self._cmd_search,
            'add': self._cmd_add,
            'recommend': self._cmd_recommend,
            'clear': self._cmd_clear,
            'save': self._cmd_save,
            'exit': lambda _: 'exit',
            'quit': lambda _: 'exit',
        }

        handler = handlers.get(command)
        if handler:
            return handler(args)
        else:
            # Treat any unrecognized input as natural language conversation
            # This makes the REPL feel more like chatting with an assistant
            if self.claude:
                return self._cmd_ask(user_input)
            else:
                self.console.print(f"[red]Unknown command: {command}[/red]")
                self.console.print("[dim]Type 'help' for commands. Set up API key with 'sherpa --setup' for natural conversation.[/dim]")
                return None

    # === Command Handlers ===

    def _cmd_load(self, args: str) -> None:
        """Load a paper"""
        if not args:
            self.console.print("[red]Usage: load <paper_id or arxiv_id>[/red]")
            return

        paper = self.kb.get_paper(args)
        if not paper:
            # Try as arxiv ID
            all_papers = self.kb.get_all_papers()
            for p in all_papers:
                if p.get('arxiv_id') == args:
                    paper = p
                    break

        if paper:
            self.current_paper = paper
            self.parsed_content = None  # Reset parsed content

            self.console.print(f"\n[green]Loaded:[/green] {paper['title']}")
            self.console.print(f"[dim]Difficulty: {paper['difficulty']} | "
                             f"Time: {paper.get('implementation_time_hours', '?')} hours | "
                             f"Value: {paper['educational_value']}[/dim]")

            if paper.get('arxiv_id'):
                self.console.print(f"\n[dim]ArXiv: {paper['arxiv_id']} - use 'fetch' to download PDF[/dim]")
        else:
            self.console.print(f"[red]Paper not found: {args}[/red]")
            self.console.print("[dim]Use 'papers' to list available papers[/dim]")

    def _cmd_fetch(self, args: str) -> None:
        """Download and parse paper PDF"""
        if not self.current_paper:
            self.console.print("[red]No paper loaded. Use 'load' first.[/red]")
            return

        arxiv_id = self.current_paper.get('arxiv_id')
        if not arxiv_id:
            self.console.print("[red]No arXiv ID for this paper.[/red]")
            return

        self.console.print(f"[dim]Fetching PDF for {arxiv_id}...[/dim]")

        try:
            self.parsed_content = self.pdf_parser.parse_from_arxiv(arxiv_id)
            self.console.print(f"\n[green]Parsed successfully![/green]")
            self.console.print(f"  Sections: {len(self.parsed_content.sections)}")
            self.console.print(f"  Algorithms: {len(self.parsed_content.algorithms)}")
            self.console.print(f"  Equations: {len(self.parsed_content.equations)}")
        except Exception as e:
            self.console.print(f"[red]Failed to fetch/parse PDF: {e}[/red]")

    def _cmd_start(self, args: str) -> None:
        """Start a new implementation session"""
        if not self.current_paper:
            self.console.print("[red]No paper loaded. Use 'load' first.[/red]")
            return

        project_path = args or f"./{self.current_paper['paper_id']}_impl"
        project_path = os.path.expanduser(project_path)

        # Generate initial stages
        stages = self._generate_stages()

        self.current_session = self.session_manager.create_session(
            paper_id=self.current_paper['paper_id'],
            project_path=project_path,
            stages=stages
        )

        # Create project directory
        Path(project_path).mkdir(parents=True, exist_ok=True)

        self.console.print(f"\n[green]Session started![/green]")
        self.console.print(f"  Session ID: {self.current_session.session_id}")
        self.console.print(f"  Project: {project_path}")
        self.console.print(f"  Stages: {len(stages)}")

        self._show_stages()

        # Initialize Claude Code
        self.claude_code = ClaudeCodeInterface(project_path)

    def _cmd_resume(self, args: str) -> None:
        """Resume an existing session"""
        if args:
            session = self.session_manager.resume_session(args)
        else:
            # Show available sessions
            sessions = self.session_manager.list_sessions()
            if not sessions:
                self.console.print("[yellow]No sessions found.[/yellow]")
                return

            self.console.print("\n[bold]Recent sessions:[/bold]")
            for s in sessions[:5]:
                self.console.print(f"  {s['session_id']}: {s['paper_title'][:40]}... ({s['status']})")

            self.console.print("\n[dim]Use 'resume <session_id>' to continue[/dim]")
            return

        if session:
            self.current_session = session
            self.current_paper = self.kb.get_paper(session.paper_id)
            self.claude_code = ClaudeCodeInterface(session.project_path)

            self.console.print(f"\n[green]Resumed session {session.session_id}[/green]")
            self._cmd_status('')
        else:
            self.console.print(f"[red]Session not found: {args}[/red]")

    def _cmd_sessions(self, args: str) -> None:
        """List all sessions"""
        sessions = self.session_manager.list_sessions()

        if not sessions:
            self.console.print("[yellow]No sessions found.[/yellow]")
            return

        table = Table(title="Implementation Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Paper")
        table.add_column("Status")
        table.add_column("Last Active")

        for s in sessions:
            table.add_row(
                s['session_id'],
                s['paper_title'][:30] + '...' if len(s['paper_title']) > 30 else s['paper_title'],
                s['status'],
                s.get('last_active_at', 'N/A')[:16] if s.get('last_active_at') else 'N/A'
            )

        self.console.print(table)

    def _cmd_status(self, args: str) -> None:
        """Show current session status"""
        if not self.current_session:
            self.console.print("[yellow]No active session. Use 'start' or 'resume'.[/yellow]")
            return

        self.console.print(f"\n[bold]Session: {self.current_session.session_id}[/bold]")
        self.console.print(f"  Paper: {self.current_paper['title'][:50]}...")
        self.console.print(f"  Path: {self.current_session.project_path}")
        self.console.print(f"  Status: {self.current_session.status}")

        self._show_stages()

    def _cmd_explain(self, args: str) -> None:
        """Explain a concept from the paper"""
        if not args:
            self.console.print("[red]Usage: explain <concept>[/red]")
            return

        if not self.claude:
            self.console.print("[red]Claude API not configured. Set ANTHROPIC_API_KEY.[/red]")
            return

        context = self._build_paper_context()
        prompt = f"""Explain the concept "{args}" from this paper.

{context}

Explain clearly and concisely, referencing the paper where relevant.
Include any relevant equations or algorithms."""

        self.console.print(f"\n[dim]Thinking...[/dim]")

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            self.console.print(Markdown(response.content[0].text))
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def _cmd_equation(self, args: str) -> None:
        """Show an equation"""
        if not self.parsed_content:
            self.console.print("[red]No PDF parsed. Use 'fetch' first.[/red]")
            return

        if not args:
            # List all equations
            self.console.print("\n[bold]Equations found:[/bold]")
            for i, eq in enumerate(self.parsed_content.equations):
                label = eq.label or f"#{i}"
                self.console.print(f"  {label}: {eq.latex[:60]}...")
            return

        try:
            idx = int(args) - 1
            eq = self.parsed_content.equations[idx]
            self.console.print(f"\n[bold]{eq.label or f'Equation {idx+1}'}[/bold]")
            self.console.print(f"\n  {eq.latex}")
            if eq.context:
                self.console.print(f"\n[dim]Context: {eq.context}[/dim]")
        except (ValueError, IndexError):
            self.console.print(f"[red]Equation not found: {args}[/red]")

    def _cmd_algorithm(self, args: str) -> None:
        """Show an algorithm"""
        if not self.parsed_content:
            self.console.print("[red]No PDF parsed. Use 'fetch' first.[/red]")
            return

        if not args:
            self.console.print("\n[bold]Algorithms found:[/bold]")
            for i, algo in enumerate(self.parsed_content.algorithms):
                self.console.print(f"  {i+1}. {algo.name}")
            return

        try:
            idx = int(args) - 1
            algo = self.parsed_content.algorithms[idx]
            self.console.print(f"\n[bold]{algo.name}[/bold]")
            self.console.print(f"\n{algo.pseudocode}")
            if algo.description:
                self.console.print(f"\n[dim]{algo.description}[/dim]")
        except (ValueError, IndexError):
            self.console.print(f"[red]Algorithm not found: {args}[/red]")

    def _cmd_ask(self, args: str) -> None:
        """Ask a question - about a paper or general ML topics"""
        if not args:
            self.console.print("[red]Usage: ask <question>[/red]")
            return

        if not self.claude:
            self.console.print("[red]Claude API not configured. Run 'sherpa --setup' first.[/red]")
            return

        # Build context based on what's loaded
        if self.current_paper:
            context = self._build_paper_context()
            prompt = f"""You are Sherpa, an AI assistant helping researchers implement ML papers.

The user is working on: {self.current_paper['title']}

Paper context:
{context}

User question: {args}

Answer helpfully, referencing the paper when relevant. If the question is general (not about this specific paper), you can answer broadly about ML/AI topics."""
        else:
            # General question - provide knowledge base context
            papers = self.kb.get_all_papers()
            paper_list = "\n".join([f"- {p['paper_id']}: {p['title']} ({p['difficulty']})" for p in papers])
            prompt = f"""You are Sherpa, an AI assistant helping researchers decide which ML papers to implement and guiding them through implementation.

Available papers in knowledge base:
{paper_list}

User question: {args}

Answer helpfully. If they're asking for recommendations, consider their question and suggest relevant papers from the list above. If it's a general ML question, answer it directly."""

        # Add to conversation history if in session
        if self.current_session:
            self.current_session.add_message('user', args)

        self.console.print(f"\n[dim]Thinking...[/dim]")

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.content[0].text
            self.console.print(Markdown(answer))

            if self.current_session:
                self.current_session.add_message('assistant', answer)
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def _cmd_summary(self, args: str) -> None:
        """Show paper summary"""
        if not self.current_paper:
            self.console.print("[red]No paper loaded.[/red]")
            return

        self.console.print(f"\n[bold]{self.current_paper['title']}[/bold]")
        self.console.print(f"\n[dim]Authors: {self.current_paper.get('authors', 'N/A')}[/dim]")
        self.console.print(f"[dim]Year: {self.current_paper.get('year', 'N/A')}[/dim]")

        if self.current_paper.get('description'):
            self.console.print(f"\n{self.current_paper['description']}")

        if self.current_paper.get('why_implement'):
            self.console.print(f"\n[bold]Why implement:[/bold] {self.current_paper['why_implement']}")

        if self.parsed_content:
            self.console.print(f"\n[bold]Abstract:[/bold]")
            self.console.print(self.parsed_content.abstract[:500] + '...')

    def _cmd_plan(self, args: str) -> None:
        """Show or generate implementation plan"""
        if not self.current_session:
            self.console.print("[yellow]No active session. Showing generic plan.[/yellow]")
            stages = self._generate_stages()
            self._show_stages(stages)
            return

        self._show_stages()

    def _cmd_stage(self, args: str) -> None:
        """Show current stage or jump to a stage"""
        if not self.current_session:
            self.console.print("[red]No active session.[/red]")
            return

        if args:
            try:
                idx = int(args) - 1
                if 0 <= idx < len(self.current_session.stages):
                    self.current_session.current_stage = idx
                    self.session_manager.save_session(self.current_session)
                    self.console.print(f"[green]Moved to stage {args}[/green]")
            except ValueError:
                self.console.print("[red]Invalid stage number.[/red]")
                return

        stage = self.current_session.get_current_stage()
        if stage:
            self.console.print(f"\n[bold]Current Stage {self.current_session.current_stage + 1}:[/bold] {stage.get('stage_name')}")
            if stage.get('description'):
                self.console.print(f"\n{stage['description']}")

    def _cmd_implement(self, args: str) -> None:
        """Invoke Claude Code to implement something"""
        if not self.claude_code or not self.claude_code.is_available:
            self.console.print("[red]Claude Code not available.[/red]")
            return

        if not args:
            self.console.print("[red]Usage: implement <description>[/red]")
            return

        context = self._build_paper_context()
        stage_info = ""
        if self.current_session:
            stage = self.current_session.get_current_stage()
            if stage:
                stage_info = f"\nCurrent stage: {stage.get('stage_name')}\n{stage.get('description', '')}"

        prompt = f"""Implement: {args}

Paper: {self.current_paper['title'] if self.current_paper else 'N/A'}
{stage_info}

{context[:2000] if context else ''}

Write clean, well-documented code."""

        self.console.print("\n[dim]Invoking Claude Code...[/dim]\n")
        result = self.claude_code.execute_task(prompt)

        if result['success']:
            self.console.print("\n[green]Implementation complete![/green]")
        else:
            self.console.print(f"\n[red]Error: {result['stderr']}[/red]")

    def _cmd_code(self, args: str) -> None:
        """Start Claude Code in interactive mode"""
        if not self.claude_code or not self.claude_code.is_available:
            self.console.print("[red]Claude Code not available.[/red]")
            return

        project_path = self.current_session.project_path if self.current_session else os.getcwd()
        self.console.print(f"[dim]Starting Claude Code in {project_path}...[/dim]")
        os.system(f"cd {project_path} && claude")

    def _cmd_files(self, args: str) -> None:
        """Show files created in this session"""
        if not self.current_session:
            self.console.print("[red]No active session.[/red]")
            return

        project_path = Path(self.current_session.project_path)
        if not project_path.exists():
            self.console.print("[yellow]Project directory doesn't exist yet.[/yellow]")
            return

        self.console.print(f"\n[bold]Files in {project_path}:[/bold]")
        for f in project_path.rglob('*'):
            if f.is_file() and not f.name.startswith('.'):
                rel_path = f.relative_to(project_path)
                self.console.print(f"  {rel_path}")

    def _cmd_done(self, args: str) -> None:
        """Mark current stage as complete"""
        if not self.current_session:
            self.console.print("[red]No active session.[/red]")
            return

        self.current_session.mark_stage_complete(notes=args if args else None)
        advanced = self.current_session.advance_stage()

        self.console.print(f"[green]Stage marked complete![/green]")

        if advanced:
            stage = self.current_session.get_current_stage()
            self.console.print(f"\n[bold]Next: Stage {self.current_session.current_stage + 1}[/bold] - {stage.get('stage_name')}")
        else:
            self.console.print("\n[bold green]All stages complete! Congratulations![/bold green]")

        self.session_manager.save_session(self.current_session)

    def _cmd_skip(self, args: str) -> None:
        """Skip current stage"""
        if not self.current_session:
            self.console.print("[red]No active session.[/red]")
            return

        if self.current_session.stages:
            self.current_session.stages[self.current_session.current_stage]['status'] = 'skipped'

        self.current_session.advance_stage()
        self.session_manager.save_session(self.current_session)
        self.console.print("[yellow]Stage skipped.[/yellow]")

    def _cmd_note(self, args: str) -> None:
        """Add a note to current stage"""
        if not self.current_session or not args:
            self.console.print("[red]Usage: note <text>[/red]")
            return

        if self.current_session.stages:
            stage = self.current_session.stages[self.current_session.current_stage]
            existing = stage.get('notes', '')
            stage['notes'] = f"{existing}\n{args}" if existing else args

        self.session_manager.save_session(self.current_session)
        self.console.print("[green]Note added.[/green]")

    def _cmd_progress(self, args: str) -> None:
        """Show implementation progress"""
        if not self.current_session:
            self.console.print("[red]No active session.[/red]")
            return

        completed = sum(1 for s in self.current_session.stages if s.get('status') == 'completed')
        total = len(self.current_session.stages)

        self.console.print(f"\n[bold]Progress: {completed}/{total} stages[/bold]")
        self._show_stages()

    def _cmd_help(self, args: str) -> None:
        """Show help"""
        self.console.print(get_command_help(args if args else None))

    def _cmd_papers(self, args: str) -> None:
        """List available papers"""
        papers = self.kb.get_all_papers()

        table = Table(title="Available Papers")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Difficulty")

        for p in papers:
            table.add_row(
                p['paper_id'],
                p['title'][:40] + '...' if len(p['title']) > 40 else p['title'],
                p['difficulty']
            )

        self.console.print(table)

    def _cmd_search(self, args: str) -> None:
        """Search arXiv for papers"""
        if not args:
            self.console.print("[red]Usage: search <query>[/red]")
            self.console.print("[dim]Example: search 'direct preference optimization'[/dim]")
            return

        self.console.print(f"\n[dim]Searching arXiv for '{args}'...[/dim]")

        try:
            results = self.arxiv.search_papers(args, max_results=10)

            if not results:
                self.console.print("[yellow]No papers found.[/yellow]")
                return

            table = Table(title=f"ArXiv Results: {args}")
            table.add_column("#", style="dim")
            table.add_column("ArXiv ID", style="cyan")
            table.add_column("Title")
            table.add_column("Year")

            for i, paper in enumerate(results, 1):
                table.add_row(
                    str(i),
                    paper['arxiv_id'],
                    paper['title'][:50] + '...' if len(paper['title']) > 50 else paper['title'],
                    paper['published'][:4]
                )

            self.console.print(table)
            self.console.print("\n[dim]Use 'add <arxiv_id>' to add a paper to your knowledge base[/dim]")

            # Store results for quick add
            self._last_search_results = results

        except Exception as e:
            self.console.print(f"[red]Search failed: {e}[/red]")

    def _cmd_add(self, args: str) -> None:
        """Add a paper from arXiv to knowledge base"""
        if not args:
            self.console.print("[red]Usage: add <arxiv_id>[/red]")
            self.console.print("[dim]Example: add 2305.18290[/dim]")
            return

        arxiv_id = args.strip()

        # Check if already in KB
        existing = self.kb.get_all_papers()
        for p in existing:
            if p.get('arxiv_id') == arxiv_id:
                self.console.print(f"[yellow]Paper already in knowledge base: {p['paper_id']}[/yellow]")
                return

        self.console.print(f"\n[dim]Fetching paper {arxiv_id} from arXiv...[/dim]")

        try:
            # Fetch from arXiv
            paper_data = self.arxiv.get_paper_by_id(arxiv_id)

            # Generate paper_id from title
            title_words = paper_data['title'].lower().split()[:3]
            paper_id = '_'.join(w for w in title_words if w.isalnum())[:20] + f"_{paper_data['published'][:4]}"

            # Estimate difficulty based on abstract keywords
            abstract_lower = paper_data['abstract'].lower()
            if any(w in abstract_lower for w in ['theoretical', 'prove', 'theorem', 'bounds']):
                difficulty = 'advanced'
            elif any(w in abstract_lower for w in ['novel', 'state-of-the-art', 'outperforms']):
                difficulty = 'intermediate'
            else:
                difficulty = 'intermediate'

            # Create KB entry
            kb_entry = {
                'paper_id': paper_id,
                'title': paper_data['title'],
                'arxiv_id': arxiv_id,
                'authors': ', '.join(paper_data['authors'][:3]) + ('...' if len(paper_data['authors']) > 3 else ''),
                'year': int(paper_data['published'][:4]),
                'difficulty': difficulty,
                'educational_value': 'high',
                'production_relevance': 'medium',
                'description': paper_data['abstract'][:500],
                'pdf_url': paper_data['pdf_url'],
            }

            # Use Claude to extract key concepts if available
            if self.claude:
                self.console.print("[dim]Analyzing paper...[/dim]")
                try:
                    response = self.claude.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=500,
                        messages=[{"role": "user", "content": f"""Analyze this ML paper abstract and extract:
1. 3-5 key concepts (as lowercase_underscore terms)
2. A one-sentence "why implement this" recommendation
3. Estimated implementation time in hours (e.g., "8-12")

Abstract: {paper_data['abstract']}

Respond in JSON format:
{{"key_concepts": ["concept1", "concept2"], "why_implement": "...", "implementation_time": "X-Y"}}"""}]
                    )
                    import json
                    analysis = json.loads(response.content[0].text)
                    kb_entry['key_concepts'] = analysis.get('key_concepts', [])
                    kb_entry['why_implement'] = analysis.get('why_implement', '')
                    kb_entry['implementation_time_hours'] = analysis.get('implementation_time', '8-16')
                except:
                    kb_entry['key_concepts'] = []
                    kb_entry['implementation_time_hours'] = '8-16'

            # Add to knowledge base
            if self.kb.add_paper(kb_entry):
                self.console.print(f"\n[green]Added paper![/green]")
                self.console.print(f"  ID: {paper_id}")
                self.console.print(f"  Title: {paper_data['title'][:60]}...")
                self.console.print(f"  Difficulty: {difficulty}")
                self.console.print(f"\n[dim]Use 'load {paper_id}' to start working with it[/dim]")
            else:
                self.console.print("[red]Failed to add paper to knowledge base.[/red]")

        except Exception as e:
            self.console.print(f"[red]Failed to fetch paper: {e}[/red]")

    def _cmd_recommend(self, args: str) -> None:
        """Get personalized paper recommendations"""
        if not self.claude:
            self.console.print("[red]Claude API required for recommendations.[/red]")
            return

        # Get user's context
        sessions = self.session_manager.list_sessions(status='completed')
        completed_papers = [s['paper_id'] for s in sessions]

        all_papers = self.kb.get_all_papers()
        paper_summaries = "\n".join([
            f"- {p['paper_id']}: {p['title']} (difficulty: {p['difficulty']}, value: {p.get('educational_value', 'unknown')})"
            for p in all_papers
        ])

        interest = args if args else "ML research and implementation"

        prompt = f"""You are Sherpa, an AI research advisor. Based on the user's interests and progress, recommend papers to implement.

User's interest: {interest}
Papers already completed: {completed_papers if completed_papers else 'None yet'}

Available papers:
{paper_summaries}

Recommend 3-5 papers in order of priority. For each:
1. Paper ID and title
2. Why it's a good fit for their interests
3. What they'll learn
4. Prerequisites (if any)

Be specific and practical. Focus on implementation value."""

        self.console.print("\n[dim]Analyzing your interests...[/dim]")

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            self.console.print(Markdown(response.content[0].text))
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def _cmd_clear(self, args: str) -> None:
        """Clear screen"""
        os.system('clear' if os.name != 'nt' else 'cls')

    def _cmd_save(self, args: str) -> None:
        """Save current session"""
        if not self.current_session:
            self.console.print("[yellow]No active session to save.[/yellow]")
            return

        self.session_manager.save_session(self.current_session)
        self.console.print("[green]Session saved.[/green]")

    def _handle_exit(self):
        """Handle exit"""
        if self.current_session:
            self.session_manager.save_session(self.current_session)
            self.console.print("[dim]Session saved.[/dim]")

        self.console.print("[dim]Goodbye![/dim]")

    # === Helper Methods ===

    def _generate_stages(self) -> List[Dict]:
        """Generate implementation stages for current paper"""
        if not self.current_paper:
            return []

        # If we have Claude and parsed content, generate smart stages
        if self.claude and self.parsed_content:
            return self._generate_smart_stages()

        # Fallback to generic stages
        stages = [
            {'stage_name': 'Setup', 'description': 'Create project structure and dependencies', 'status': 'not_started'},
            {'stage_name': 'Data', 'description': 'Implement data loading and preprocessing', 'status': 'not_started'},
            {'stage_name': 'Model', 'description': 'Implement core model/algorithm', 'status': 'not_started'},
            {'stage_name': 'Training', 'description': 'Implement training loop', 'status': 'not_started'},
            {'stage_name': 'Evaluation', 'description': 'Implement evaluation and metrics', 'status': 'not_started'},
        ]

        # Customize based on paper keywords
        paper_id = self.current_paper.get('paper_id', '').lower()
        if 'dpo' in paper_id or 'preference' in paper_id:
            stages[1]['description'] = 'Implement preference dataset (chosen/rejected pairs)'
            stages[2]['description'] = 'Implement DPO loss function'
            stages.insert(3, {'stage_name': 'Reference Model', 'description': 'Set up reference model for KL constraint', 'status': 'not_started'})

        return stages

    def _generate_smart_stages(self) -> List[Dict]:
        """Generate paper-specific implementation stages using Claude"""
        self.console.print("[dim]Generating paper-specific implementation plan...[/dim]")

        # Build context from parsed content
        algorithms = "\n".join([f"- {a.name}: {a.pseudocode[:200]}..." for a in self.parsed_content.algorithms[:5]])
        equations = "\n".join([f"- {e.label or 'Eq'}: {e.latex[:100]}" for e in self.parsed_content.equations[:8]])

        prompt = f"""Analyze this ML paper and create a detailed implementation plan.

Paper: {self.current_paper['title']}

Abstract: {self.parsed_content.abstract[:1000]}

Key Algorithms:
{algorithms if algorithms else 'Not explicitly extracted'}

Key Equations:
{equations if equations else 'Not explicitly extracted'}

Create 5-7 implementation stages. Each stage should be:
- Specific to THIS paper (not generic)
- Focused on one clear component
- Ordered from foundational to advanced

Return as JSON array:
[
  {{"stage_name": "Short Name", "description": "What to implement and key details", "key_files": ["file1.py"], "estimated_hours": 2}},
  ...
]

Be specific! Reference actual algorithms/equations from the paper."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON from response
            import json
            response_text = response.content[0].text

            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            stages_data = json.loads(response_text)

            # Convert to our format
            stages = []
            for s in stages_data:
                stages.append({
                    'stage_name': s.get('stage_name', 'Stage'),
                    'description': s.get('description', ''),
                    'key_files': s.get('key_files', []),
                    'estimated_hours': s.get('estimated_hours', 2),
                    'status': 'not_started'
                })

            return stages

        except Exception as e:
            self.console.print(f"[yellow]Smart planning failed, using defaults: {e}[/yellow]")
            # Fall back to generic stages
            return [
                {'stage_name': 'Setup', 'description': 'Create project structure and dependencies', 'status': 'not_started'},
                {'stage_name': 'Data', 'description': 'Implement data loading and preprocessing', 'status': 'not_started'},
                {'stage_name': 'Model', 'description': 'Implement core model/algorithm', 'status': 'not_started'},
                {'stage_name': 'Training', 'description': 'Implement training loop', 'status': 'not_started'},
                {'stage_name': 'Evaluation', 'description': 'Implement evaluation and metrics', 'status': 'not_started'},
            ]

    def _show_stages(self, stages: List[Dict] = None):
        """Display implementation stages"""
        stages = stages or (self.current_session.stages if self.current_session else [])

        if not stages:
            self.console.print("[yellow]No stages defined.[/yellow]")
            return

        current = self.current_session.current_stage if self.current_session else -1

        self.console.print("\n[bold]Implementation Stages:[/bold]")
        for i, stage in enumerate(stages):
            status = stage.get('status', 'not_started')
            marker = '→' if i == current else ' '
            status_icon = {'completed': '✓', 'in_progress': '●', 'skipped': '○'}.get(status, '○')
            style = 'green' if status == 'completed' else ('yellow' if i == current else 'dim')

            self.console.print(f"  [{style}]{marker} {i+1}. {status_icon} {stage.get('stage_name')}[/{style}]")

    def _build_paper_context(self) -> str:
        """Build context string for Claude prompts"""
        parts = []

        if self.current_paper:
            parts.append(f"Paper: {self.current_paper['title']}")
            if self.current_paper.get('description'):
                parts.append(f"Description: {self.current_paper['description']}")

        if self.parsed_content:
            parts.append(f"\nAbstract: {self.parsed_content.abstract[:1000]}")

            if self.parsed_content.algorithms:
                parts.append("\nKey algorithms:")
                for algo in self.parsed_content.algorithms[:3]:
                    parts.append(f"- {algo.name}")

            if self.parsed_content.equations:
                parts.append("\nKey equations:")
                for eq in self.parsed_content.equations[:5]:
                    parts.append(f"- {eq.label or 'Equation'}: {eq.latex[:100]}")

        return '\n'.join(parts)


def start_repl():
    """Entry point for starting the REPL"""
    repl = ImplementationREPL()
    repl.run()


if __name__ == "__main__":
    start_repl()
