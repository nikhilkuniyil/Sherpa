#!/usr/bin/env python3
"""
TutoringEngine - Main orchestrator for the interactive tutoring system.
Routes user input to appropriate mode handlers and manages session state.
"""

import json
import re
from typing import Optional, Dict, TYPE_CHECKING

from .state import (
    TutoringMode,
    TutoringPhase,
    TutoringState,
    TutoringResponse,
    CodeSkeleton,
    TodoItem,
)
from . import prompts

if TYPE_CHECKING:
    from anthropic import Anthropic


class TutoringEngine:
    """Orchestrates the tutoring flow based on mode and state"""

    def __init__(
        self,
        claude_client: 'Anthropic',
        mode: str = 'tutorial',
        paper_title: str = '',
        paper_context: str = ''
    ):
        self.claude = claude_client
        self.paper_title = paper_title
        self.paper_context = paper_context
        self.state = TutoringState(mode=self._parse_mode(mode))

        # Import mode handlers (avoid circular imports)
        from .modes import (
            TutorialModeHandler,
            GuidedModeHandler,
            ChallengeModeHandler,
            DebugModeHandler,
        )

        self.mode_handlers = {
            TutoringMode.TUTORIAL: TutorialModeHandler(self),
            TutoringMode.GUIDED: GuidedModeHandler(self),
            TutoringMode.CHALLENGE: ChallengeModeHandler(self),
            TutoringMode.DEBUG: DebugModeHandler(self),
        }

    def _parse_mode(self, mode: str) -> TutoringMode:
        """Parse mode string to TutoringMode enum"""
        mode_map = {
            'tutorial': TutoringMode.TUTORIAL,
            'guided': TutoringMode.GUIDED,
            'challenge': TutoringMode.CHALLENGE,
            'debug': TutoringMode.DEBUG,
        }
        return mode_map.get(mode.lower(), TutoringMode.TUTORIAL)

    def set_paper_context(self, title: str, context: str):
        """Update paper context (called when paper is loaded)"""
        self.paper_title = title
        self.paper_context = context

    def get_mode_handler(self):
        """Get the current mode's handler"""
        return self.mode_handlers[self.state.mode]

    def is_active(self) -> bool:
        """Check if tutoring session is active (not in init phase)"""
        return self.state.phase != TutoringPhase.INIT

    def process_input(self, user_input: str) -> TutoringResponse:
        """Main entry point - routes input based on current state"""
        user_input = user_input.strip()

        # Handle special commands that work in any phase
        lower_input = user_input.lower()

        # Hint request
        if lower_input in ['hint', 'hint please', "i'm stuck", 'stuck', 'help me']:
            return self._give_hint()

        # Skip/give up
        if lower_input in ['skip', 'show me', 'give up', 'answer']:
            return self._skip_to_answer()

        # Mode switch
        if lower_input.startswith('mode '):
            return self._switch_mode(lower_input[5:].strip())

        # Exit tutoring
        if lower_input in ['exit learn', 'stop', 'quit learning', 'done learning']:
            return self._exit_tutoring()

        # Route to mode handler based on current phase
        handler = self.get_mode_handler()
        return handler.handle(user_input, self.state)

    def start_learning(self, concept: str = '') -> TutoringResponse:
        """Begin a new learning session for a concept"""
        if not self.paper_context:
            return TutoringResponse.error(
                "No paper loaded. Use 'load <paper_id>' first."
            )

        # Use paper title as concept if not specified
        concept = concept or self.paper_title

        # Reset state for new concept
        self.state.reset_for_new_concept(concept)

        # Start with the appropriate mode handler
        handler = self.get_mode_handler()
        return handler.start_concept(concept, self.state)

    def _give_hint(self) -> TutoringResponse:
        """Provide a hint based on current context"""
        if self.state.phase not in [TutoringPhase.SKELETON, TutoringPhase.TODO_REVIEW]:
            return TutoringResponse(
                message="Hints are available when you're working on a TODO. "
                        "Type your answer or code to continue.",
                waiting_for='input'
            )

        todo = self.state.get_current_todo()
        if not todo:
            return TutoringResponse(
                message="No active TODO to give hints for.",
                waiting_for='input'
            )

        # Progress through hint levels
        current_level = self.state.metrics.current_hint_level

        if current_level == 0:
            # Level 1: Conceptual hint
            hint = todo.hint_l1 or "Think about the goal: " + todo.goal
            self.state.metrics.current_hint_level = 1
            return TutoringResponse(
                message=f"**Hint (Level 1 - Conceptual):**\n\n{hint}",
                waiting_for='code',
                prompt_hint="Try again with this hint in mind..."
            )

        elif current_level == 1:
            # Level 2: Specific direction
            hint = todo.hint_l2 or "Focus on: " + todo.goal
            self.state.metrics.current_hint_level = 2
            return TutoringResponse(
                message=f"**Hint (Level 2 - More Specific):**\n\n{hint}",
                waiting_for='code',
                prompt_hint="One more try..."
            )

        else:
            # Level 3: Show the answer
            self.state.metrics.current_hint_level = 3
            self.state.metrics.todos_needed_hints += 1
            solution = todo.solution or "[Solution not available]"
            return TutoringResponse(
                message=f"**Here's the solution:**\n\n```python\n{solution}\n```\n\n"
                        f"Take a moment to understand why this works, then type 'next' to continue.",
                waiting_for='input',
                prompt_hint="Type 'next' when ready to continue"
            )

    def _skip_to_answer(self) -> TutoringResponse:
        """Skip directly to showing the answer"""
        todo = self.state.get_current_todo()
        if not todo:
            return TutoringResponse(
                message="Nothing to skip - no active TODO.",
                waiting_for='input'
            )

        self.state.metrics.current_hint_level = 3
        self.state.metrics.todos_needed_hints += 1
        solution = todo.solution or "[Solution not available]"

        return TutoringResponse(
            message=f"**Solution for TODO {todo.id}:**\n\n```python\n{solution}\n```\n\n"
                    f"Study this, then type 'next' to continue to the next TODO.",
            waiting_for='input',
            prompt_hint="Type 'next' when ready"
        )

    def _switch_mode(self, new_mode: str) -> TutoringResponse:
        """Switch tutoring mode"""
        try:
            mode = self._parse_mode(new_mode)
            old_mode = self.state.mode
            self.state.mode = mode

            # Reset phase for new mode
            if self.state.phase != TutoringPhase.INIT:
                self.state.phase = TutoringPhase.INIT

            mode_descriptions = {
                TutoringMode.TUTORIAL: "Tutorial mode - I'll guide you with code skeletons and TODOs",
                TutoringMode.GUIDED: "Guided mode - I'll explain everything fully",
                TutoringMode.CHALLENGE: "Challenge mode - You write from scratch, I review",
                TutoringMode.DEBUG: "Debug mode - I'll give you buggy code to fix",
            }

            return TutoringResponse(
                message=f"Switched from {old_mode.value} to **{mode.value}** mode.\n\n"
                        f"{mode_descriptions[mode]}\n\n"
                        f"Type 'learn' to start with this mode.",
                waiting_for='input'
            )

        except Exception as e:
            return TutoringResponse.error(
                f"Unknown mode '{new_mode}'. Available: tutorial, guided, challenge, debug"
            )

    def _exit_tutoring(self) -> TutoringResponse:
        """Exit the tutoring session"""
        # Summarize progress
        metrics = self.state.metrics
        completed = len(self.state.completed_concepts)

        summary_parts = []
        if completed > 0:
            summary_parts.append(f"Concepts completed: {completed}")
        if metrics.todos_first_try + metrics.todos_needed_hints > 0:
            summary_parts.append(
                f"TODOs: {metrics.todos_first_try} first-try, "
                f"{metrics.todos_needed_hints} with hints"
            )
        if metrics.checkpoints_passed + metrics.checkpoints_failed > 0:
            summary_parts.append(
                f"Checkpoints: {metrics.checkpoints_passed} passed, "
                f"{metrics.checkpoints_failed} to review"
            )

        summary = "\n".join(summary_parts) if summary_parts else "Session ended early"

        # Reset to init
        self.state.phase = TutoringPhase.INIT

        return TutoringResponse(
            message=f"**Learning session ended.**\n\n{summary}\n\n"
                    f"Use 'learn' to start a new session, or continue with other commands.",
            waiting_for='input'
        )

    # =========================================================================
    # Claude API helpers
    # =========================================================================

    def call_claude(self, prompt: str, max_tokens: int = 2000) -> str:
        """Make a Claude API call and return the response text"""
        if not self.claude:
            return '{"error": "Claude API not available"}'

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    def call_claude_json(self, prompt: str, max_tokens: int = 2000) -> Dict:
        """Make a Claude API call and parse JSON response"""
        response_text = self.call_claude(prompt, max_tokens)

        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if '```json' in response_text:
                match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
            elif '```' in response_text:
                match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))

            # Try parsing directly
            return json.loads(response_text)

        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON response", "raw": response_text}

    def stream_claude(self, prompt: str, max_tokens: int = 2000):
        """Stream Claude response (returns generator)"""
        if not self.claude:
            yield "[Claude API not available]"
            return

        try:
            with self.claude.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            yield f"[Error: {str(e)}]"
