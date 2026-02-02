#!/usr/bin/env python3
"""
Claude Code integration for direct code implementation.
Invokes Claude Code CLI as a subprocess to write/edit files.
"""

import subprocess
import os
import shutil
from typing import List, Optional, Dict
from pathlib import Path


class ClaudeCodeInterface:
    """Interface for invoking Claude Code as a subprocess"""

    def __init__(self, working_dir: str = None):
        self.working_dir = working_dir or os.getcwd()
        self._claude_path = None
        self._verify_installation()

    def _verify_installation(self):
        """Check if Claude Code CLI is available"""
        # Try to find claude in PATH
        self._claude_path = shutil.which('claude')

        if not self._claude_path:
            # Common installation locations
            possible_paths = [
                '/usr/local/bin/claude',
                os.path.expanduser('~/.local/bin/claude'),
                os.path.expanduser('~/bin/claude'),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    self._claude_path = path
                    break

        if not self._claude_path:
            print("Warning: Claude Code CLI not found in PATH.")
            print("Install with: npm install -g @anthropic-ai/claude-code")
            print("Or ensure 'claude' is in your PATH.")

    @property
    def is_available(self) -> bool:
        """Check if Claude Code is available"""
        return self._claude_path is not None

    def execute_task(
        self,
        prompt: str,
        context_files: List[str] = None,
        timeout: int = 300,
        print_output: bool = True
    ) -> Dict:
        """
        Execute a task via Claude Code CLI.

        Args:
            prompt: The task description/prompt
            context_files: Optional list of files to include as context
            timeout: Max execution time in seconds
            print_output: Whether to print Claude's output in real-time

        Returns:
            Dict with 'success', 'output', 'stderr', 'returncode'
        """
        if not self.is_available:
            return {
                'success': False,
                'output': '',
                'stderr': 'Claude Code CLI not installed',
                'returncode': -1
            }

        # Build command
        cmd = [self._claude_path, '-p', prompt]

        # Add working directory
        if self.working_dir:
            cmd.extend(['--cwd', self.working_dir])

        # Execute with real-time output if requested
        try:
            if print_output:
                # Run with inherited stdout/stderr for interactive experience
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    timeout=timeout,
                    capture_output=False,  # Let output flow to terminal
                    text=True
                )
                return {
                    'success': result.returncode == 0,
                    'output': '[Output shown in terminal]',
                    'stderr': '',
                    'returncode': result.returncode
                }
            else:
                # Capture output silently
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.working_dir
                )
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'stderr': f'Task timed out after {timeout} seconds',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'stderr': str(e),
                'returncode': -1
            }

    def implement_component(
        self,
        component_name: str,
        file_path: str,
        description: str,
        algorithm: str = None,
        equations: List[str] = None,
        context: str = None
    ) -> Dict:
        """
        Implement a specific component based on paper content.

        Args:
            component_name: Name of the component to implement
            file_path: Target file path
            description: Description of what to implement
            algorithm: Algorithm pseudocode from paper
            equations: Key equations to implement
            context: Additional context about the paper/approach

        Returns:
            Result dict from execute_task
        """
        prompt_parts = [
            f"Implement '{component_name}' in {file_path}.",
            "",
            f"Description: {description}",
        ]

        if context:
            prompt_parts.extend(["", f"Context: {context}"])

        if algorithm:
            prompt_parts.extend([
                "",
                "Algorithm from paper:",
                "```",
                algorithm,
                "```"
            ])

        if equations:
            prompt_parts.extend([
                "",
                "Key equations to implement:",
            ])
            for eq in equations:
                prompt_parts.append(f"  - {eq}")

        prompt_parts.extend([
            "",
            "Requirements:",
            "- Write clean, well-documented Python code",
            "- Include docstrings explaining the implementation",
            "- Add comments referencing the paper where relevant",
            "- Make the code modular and testable"
        ])

        prompt = "\n".join(prompt_parts)
        return self.execute_task(prompt)

    def create_project_structure(
        self,
        paper_title: str,
        stages: List[Dict],
        base_path: str = None
    ) -> Dict:
        """
        Create initial project structure for paper implementation.

        Args:
            paper_title: Title of the paper
            stages: Implementation stages with descriptions
            base_path: Optional base path (defaults to working_dir)

        Returns:
            Result dict
        """
        path = base_path or self.working_dir

        stage_desc = "\n".join([
            f"  {i+1}. {s.get('stage_name', f'Stage {i+1}')}: {s.get('description', '')}"
            for i, s in enumerate(stages)
        ])

        prompt = f"""Create a project structure for implementing the paper: "{paper_title}"

Project path: {path}

Implementation stages:
{stage_desc}

Create:
1. A clear directory structure (src/, tests/, etc.)
2. An __init__.py with basic module setup
3. A README.md explaining the implementation plan
4. Placeholder files for each major component

Keep it minimal but well-organized."""

        return self.execute_task(prompt)

    def explain_and_implement(
        self,
        concept: str,
        paper_context: str,
        target_file: str
    ) -> Dict:
        """
        Have Claude explain a concept and then implement it.

        Args:
            concept: The concept to explain and implement
            paper_context: Context from the paper
            target_file: Where to implement

        Returns:
            Result dict
        """
        prompt = f"""I'm implementing a paper and need help with: {concept}

Paper context:
{paper_context}

Please:
1. First explain the concept clearly
2. Then implement it in {target_file}
3. Add comments linking the code to the paper's description

Make the implementation clear and educational."""

        return self.execute_task(prompt)


def check_claude_code_available() -> bool:
    """Quick check if Claude Code CLI is available"""
    return shutil.which('claude') is not None
