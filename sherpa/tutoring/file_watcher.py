#!/usr/bin/env python3
"""
File watcher for tutorial mode.
Monitors implementation files and provides feedback as the user completes TODOs.
"""

import os
import re
import time
import threading
from pathlib import Path
from typing import Optional, Set, Dict, List, Callable
from dataclasses import dataclass, field

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown


@dataclass
class TutorialSession:
    """Tracks the state of a file-based tutorial session"""
    filepath: str
    topic: str
    total_todos: int = 0
    reviewed_todos: Set[int] = field(default_factory=set)
    current_todo: int = 1
    checkpoint_pending: bool = False
    checkpoint_question: str = ""
    all_complete: bool = False


class SherpaFileReviewer(FileSystemEventHandler):
    """Watches implementation file and reviews completed TODOs"""

    DEBOUNCE_SECONDS = 1.5

    def __init__(
        self,
        filepath: str,
        session: TutorialSession,
        llm_client,
        paper_context: str = "",
        console: Console = None,
    ):
        super().__init__()
        self.filepath = os.path.abspath(filepath)
        self.session = session
        self.llm = llm_client
        self.paper_context = paper_context
        self.console = console or Console()
        self.last_modified = 0
        self.last_content = ""
        self._reviewing = False

    def on_modified(self, event):
        """Called when the watched file is modified"""
        if not isinstance(event, FileModifiedEvent):
            return

        # Check if it's our file
        event_path = os.path.abspath(event.src_path)
        if event_path != self.filepath:
            return

        # Debounce - wait for user to stop typing/saving
        current_time = time.time()
        if current_time - self.last_modified < self.DEBOUNCE_SECONDS:
            return
        self.last_modified = current_time

        # Don't process if already reviewing
        if self._reviewing:
            return

        # Read the file
        try:
            with open(self.filepath, 'r') as f:
                code = f.read()
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")
            return

        # Skip if content hasn't changed
        if code == self.last_content:
            return
        self.last_content = code

        # Run review in a separate thread to not block
        thread = threading.Thread(target=self._review_changes, args=(code,))
        thread.daemon = True
        thread.start()

    def _review_changes(self, code: str):
        """Review the code changes"""
        self._reviewing = True

        try:
            # Identify which TODO was just completed
            completed_todo = self._identify_completed_todo(code)

            if completed_todo is None:
                return

            if completed_todo in self.session.reviewed_todos:
                return

            self.console.print(f"\n[dim]{'─' * 70}[/dim]")
            self.console.print(f"[cyan]Reviewing TODO {completed_todo}...[/cyan]")

            # Get feedback from LLM
            feedback = self._get_todo_feedback(code, completed_todo)

            # Display feedback
            self._display_feedback(completed_todo, feedback)

            # Check if all TODOs are complete
            if len(self.session.reviewed_todos) >= self.session.total_todos:
                self.session.all_complete = True
                self._show_completion_message()

        finally:
            self._reviewing = False

    def _identify_completed_todo(self, code: str) -> Optional[int]:
        """
        Identify which TODO the user just completed.
        Returns the TODO number or None if no new TODO was completed.
        """
        # Find all TODO markers
        todo_pattern = r'#\s*TODO\s*(\d+)[:\s]'
        todos = re.findall(todo_pattern, code, re.IGNORECASE)

        if not todos:
            return None

        # Update total count
        self.session.total_todos = max(self.session.total_todos, len(todos))

        # Check each TODO to see if it has code (not just 'pass')
        for todo_num_str in todos:
            todo_num = int(todo_num_str)

            # Skip already reviewed TODOs
            if todo_num in self.session.reviewed_todos:
                continue

            # Check if this TODO has real implementation
            if self._todo_has_implementation(code, todo_num):
                return todo_num

        return None

    def _todo_has_implementation(self, code: str, todo_num: int) -> bool:
        """Check if a TODO section has been filled with real code"""
        # Find the TODO comment and check what follows
        pattern = rf'#\s*TODO\s*{todo_num}[:\s].*?(?=#\s*TODO\s*\d+|class\s+|def\s+\w+\s*\(|$)'
        match = re.search(pattern, code, re.DOTALL | re.IGNORECASE)

        if not match:
            return False

        section = match.group(0)

        # Remove comments and check for actual code
        lines = section.split('\n')
        code_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip empty lines, comments, and the TODO itself
            if stripped and not stripped.startswith('#'):
                code_lines.append(stripped)

        # Check if there's more than just 'pass'
        non_pass_lines = [l for l in code_lines if l != 'pass']

        return len(non_pass_lines) > 0

    def _get_todo_feedback(self, code: str, todo_num: int) -> Dict:
        """Get LLM feedback on a completed TODO"""
        if not self.llm:
            return {
                "correct": True,
                "feedback": "LLM not available for review.",
                "explanation": ""
            }

        prompt = f"""You are reviewing a student's implementation of TODO {todo_num} in a {self.session.topic} implementation.

Paper/Topic Context:
{self.paper_context[:2000] if self.paper_context else self.session.topic}

Here is their current code:
```python
{code}
```

Review ONLY TODO {todo_num}. Evaluate:
1. Is the implementation correct for what TODO {todo_num} asks?
2. Are there any bugs or issues?
3. Does it follow good practices?

IMPORTANT RULES:
- If correct: Explain WHY it works to build intuition (2-3 sentences)
- If incorrect: Give a HINT, not the answer. Guide them to figure it out.
- Be encouraging but honest
- Keep response concise (under 150 words)

Return JSON:
{{
  "correct": true/false,
  "feedback": "Your feedback message",
  "hint": "If incorrect, a hint to help them (null if correct)",
  "explanation": "If correct, why it works (null if incorrect)"
}}"""

        try:
            response = self.llm.messages.create(
                model="default",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse JSON from response
            import json

            # Try to extract JSON
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
            elif '```' in response_text:
                json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))

            # Try direct parse
            try:
                return json.loads(response_text)
            except:
                # Fallback - treat as positive feedback
                return {
                    "correct": True,
                    "feedback": response_text,
                    "explanation": ""
                }

        except Exception as e:
            return {
                "correct": True,
                "feedback": f"Review completed. (Error: {e})",
                "explanation": ""
            }

    def _display_feedback(self, todo_num: int, feedback: Dict):
        """Display the feedback to the user"""
        is_correct = feedback.get("correct", False)

        if is_correct:
            # Mark as reviewed
            self.session.reviewed_todos.add(todo_num)
            self.session.current_todo = todo_num + 1

            # Success message
            self.console.print(f"\n[green]TODO {todo_num} Complete![/green]")

            message = feedback.get("feedback", "")
            explanation = feedback.get("explanation", "")

            if explanation:
                message += f"\n\n**Why it works:** {explanation}"

            self.console.print(Panel(
                Markdown(message),
                title=f"[green]TODO {todo_num}[/green]",
                border_style="green"
            ))

            # Show progress
            reviewed = len(self.session.reviewed_todos)
            total = self.session.total_todos
            self.console.print(f"\n[dim]Progress: {reviewed}/{total} TODOs complete[/dim]")

            if reviewed < total:
                self.console.print(f"[cyan]Next: TODO {self.session.current_todo}[/cyan]")

        else:
            # Needs work
            self.console.print(f"\n[yellow]TODO {todo_num} needs some work[/yellow]")

            message = feedback.get("feedback", "Check your implementation.")
            hint = feedback.get("hint", "")

            if hint:
                message += f"\n\n**Hint:** {hint}"

            self.console.print(Panel(
                Markdown(message),
                title=f"[yellow]TODO {todo_num}[/yellow]",
                border_style="yellow"
            ))

            self.console.print("[dim]Update your code and save to try again.[/dim]")

    def _show_completion_message(self):
        """Show message when all TODOs are complete"""
        self.console.print(f"\n[bold green]{'=' * 70}[/bold green]")
        self.console.print("[bold green]Congratulations! All TODOs complete![/bold green]")
        self.console.print(f"[bold green]{'=' * 70}[/bold green]")
        self.console.print(f"\nYou've successfully implemented {self.session.topic}!")
        self.console.print("\nNext steps:")
        self.console.print("  1. Run your implementation to test it")
        self.console.print("  2. Try different hyperparameters")
        self.console.print("  3. Use 'sherpa --mode challenge' to test without hints")
        self.console.print("\n[dim]Press Ctrl+C to exit[/dim]")


class FileWatcher:
    """Manages the file watching process"""

    def __init__(
        self,
        filepath: str,
        session: TutorialSession,
        llm_client,
        paper_context: str = "",
        console: Console = None,
    ):
        self.filepath = filepath
        self.session = session
        self.llm = llm_client
        self.paper_context = paper_context
        self.console = console or Console()
        self.observer = None
        self.handler = None

    def start(self):
        """Start watching the file"""
        self.handler = SherpaFileReviewer(
            filepath=self.filepath,
            session=self.session,
            llm_client=self.llm,
            paper_context=self.paper_context,
            console=self.console,
        )

        self.observer = Observer()
        watch_dir = os.path.dirname(os.path.abspath(self.filepath))
        self.observer.schedule(self.handler, path=watch_dir, recursive=False)
        self.observer.start()

        self.console.print(f"\n[green]Watching {os.path.basename(self.filepath)} for changes...[/green]")
        self.console.print("[dim]I'll review your work each time you save the file.[/dim]")

    def stop(self):
        """Stop watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()

    def wait(self):
        """Wait until all TODOs are complete or interrupted"""
        try:
            while not self.session.all_complete:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.console.print("\n[dim]Stopping file watcher...[/dim]")
        finally:
            self.stop()
