#!/usr/bin/env python3
"""
Mode handlers for the interactive tutoring system.
Each mode implements a different pedagogical approach.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional

from .state import (
    TutoringPhase,
    TutoringState,
    TutoringResponse,
    CodeSkeleton,
    TodoItem,
)
from . import prompts

if TYPE_CHECKING:
    from .engine import TutoringEngine


class BaseModeHandler(ABC):
    """Base class for mode handlers"""

    def __init__(self, engine: 'TutoringEngine'):
        self.engine = engine

    @abstractmethod
    def start_concept(self, concept: str, state: TutoringState) -> TutoringResponse:
        """Start learning a new concept in this mode"""
        pass

    @abstractmethod
    def handle(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Handle user input based on current phase"""
        pass


class TutorialModeHandler(BaseModeHandler):
    """
    Tutorial Mode (DEFAULT) - Scaffolded learning with code skeletons.

    Flow:
    1. Why Before How - Ask user to reason about approach
    2. Show code skeleton with TODOs
    3. User fills in TODOs one at a time
    4. Evaluate each submission, give feedback
    5. Checkpoint questions between major sections
    """

    def start_concept(self, concept: str, state: TutoringState) -> TutoringResponse:
        """Start with a 'why before how' question"""
        state.phase = TutoringPhase.WHY_BEFORE_HOW

        # Generate the why question
        prompt = prompts.WHY_BEFORE_HOW_PROMPT.format(
            concept=concept,
            paper_title=self.engine.paper_title,
            paper_context=self.engine.paper_context[:3000]
        )

        why_question = self.engine.call_claude(prompt, max_tokens=800)

        state.why_question_asked = True
        state.awaiting_response = 'reasoning'

        return TutoringResponse(
            message=why_question,
            waiting_for='reasoning',
            prompt_hint="Think about the approach before we code..."
        )

    def handle(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Route based on current phase"""
        # Handle 'next' command to advance after seeing solution
        if user_input.lower() == 'next':
            return self._advance_to_next(state)

        if state.phase == TutoringPhase.WHY_BEFORE_HOW:
            return self._handle_why_response(user_input, state)
        elif state.phase == TutoringPhase.SKELETON:
            return self._handle_todo_submission(user_input, state)
        elif state.phase == TutoringPhase.TODO_REVIEW:
            return self._handle_todo_submission(user_input, state)
        elif state.phase == TutoringPhase.CHECKPOINT:
            return self._handle_checkpoint_response(user_input, state)
        elif state.phase == TutoringPhase.COMPLETE:
            return TutoringResponse(
                message="You've completed this concept! Use 'learn' to start another, "
                        "or explore other commands.",
                waiting_for='input'
            )
        else:
            return TutoringResponse(
                message="Ready to learn? Type 'learn' to start.",
                waiting_for='input'
            )

    def _handle_why_response(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Evaluate user's reasoning and show first skeleton"""
        # Get key insight for the concept
        insight_prompt = f"""What is the key insight of {state.current_concept} from "{self.engine.paper_title}"?
Summarize in 1-2 sentences the core idea that makes this approach work.

Paper context:
{self.engine.paper_context[:2000]}"""

        key_insight = self.engine.call_claude(insight_prompt, max_tokens=300)

        # Evaluate their response
        eval_prompt = prompts.EVALUATE_WHY_RESPONSE_PROMPT.format(
            concept=state.current_concept,
            paper_title=self.engine.paper_title,
            key_insight=key_insight,
            user_response=user_input
        )

        eval_result = self.engine.call_claude_json(eval_prompt)
        feedback = eval_result.get('feedback', 'Good thinking!')
        bridge = eval_result.get('bridge_to_paper', '')

        # Generate the first skeleton
        skeleton = self._generate_skeleton(state)

        if skeleton:
            state.current_skeleton = skeleton
            state.phase = TutoringPhase.SKELETON
            state.current_todo_index = 0

            first_todo = skeleton.todos[0] if skeleton.todos else None
            todo_hint = f"\n\nComplete TODO 1: {first_todo.goal}" if first_todo else ""

            return TutoringResponse(
                message=f"{feedback}\n\n{bridge}\n\n"
                        f"Here's your first code skeleton:\n\n```python\n{skeleton.code}\n```"
                        f"{todo_hint}",
                waiting_for='code',
                prompt_hint=f"Implement TODO 1..." if first_todo else "Review the skeleton"
            )
        else:
            return TutoringResponse.error("Failed to generate code skeleton. Try again with 'learn'.")

    def _generate_skeleton(self, state: TutoringState) -> Optional[CodeSkeleton]:
        """Generate a code skeleton for the current concept"""
        prompt = prompts.SKELETON_GENERATION_PROMPT.format(
            concept=state.current_concept,
            paper_title=self.engine.paper_title,
            paper_context=self.engine.paper_context[:4000]
        )

        result = self.engine.call_claude_json(prompt, max_tokens=3000)

        if 'error' in result:
            return None

        # Parse into CodeSkeleton
        todos = []
        for todo_data in result.get('todos', []):
            todos.append(TodoItem(
                id=todo_data.get('id', len(todos) + 1),
                goal=todo_data.get('goal', ''),
                hint_l1=todo_data.get('hint_l1', ''),
                hint_l2=todo_data.get('hint_l2', ''),
                solution=todo_data.get('solution', ''),
            ))

        return CodeSkeleton(
            code=result.get('code', ''),
            todos=todos,
            concept=state.current_concept,
            dependencies=result.get('concept_dependencies', [])
        )

    def _handle_todo_submission(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Evaluate user's TODO submission"""
        todo = state.get_current_todo()
        if not todo:
            return self._show_completion_or_checkpoint(state)

        state.user_code_attempt = user_input
        state.attempt_count += 1

        # Evaluate the submission
        prompt = prompts.EVALUATE_TODO_PROMPT.format(
            concept=state.current_concept,
            paper_title=self.engine.paper_title,
            todo_id=todo.id,
            todo_goal=todo.goal,
            expected_solution=todo.solution,
            user_code=user_input,
            skeleton_code=state.current_skeleton.code if state.current_skeleton else ''
        )

        result = self.engine.call_claude_json(prompt)

        if result.get('correct', False):
            # Mark TODO as complete
            todo.completed = True
            first_try = state.attempt_count == 1 and state.metrics.current_hint_level == 0
            state.metrics.record_todo_result(first_try, state.current_concept)

            # Check if we should ask a checkpoint question
            if self._should_checkpoint(state):
                return self._ask_checkpoint(state, result.get('feedback', 'Correct!'))

            # Advance to next TODO
            if state.advance_todo():
                next_todo = state.get_current_todo()
                state.metrics.current_hint_level = 0
                return TutoringResponse(
                    message=f"**Correct!** {result.get('feedback', '')}\n\n"
                            f"Next up - TODO {next_todo.id}: {next_todo.goal}",
                    waiting_for='code',
                    prompt_hint=f"Implement TODO {next_todo.id}..."
                )
            else:
                return self._show_completion_or_checkpoint(state)
        else:
            # Incorrect - give feedback
            issue = result.get('issue_detail', '')
            hint = result.get('hint_if_wrong', '')

            # Check if we should proactively offer hint
            proactive_hint = ""
            if state.metrics.should_offer_hint_proactively() and state.attempt_count >= 2:
                proactive_hint = "\n\nType 'hint' if you'd like some guidance."

            return TutoringResponse(
                message=f"**Not quite.** {result.get('feedback', '')}\n\n"
                        f"{issue}\n\n{hint}{proactive_hint}",
                waiting_for='code',
                prompt_hint=f"Try TODO {todo.id} again..."
            )

    def _should_checkpoint(self, state: TutoringState) -> bool:
        """Determine if we should ask a checkpoint question"""
        if not state.current_skeleton:
            return False

        # Ask checkpoint after every 2-3 TODOs
        completed = sum(1 for t in state.current_skeleton.todos if t.completed)
        return completed > 0 and completed % 2 == 0

    def _ask_checkpoint(self, state: TutoringState, prior_feedback: str) -> TutoringResponse:
        """Generate and ask a checkpoint question"""
        # Get recently covered concepts
        completed_todos = [t for t in state.current_skeleton.todos if t.completed]
        recent = [t.goal for t in completed_todos[-3:]]

        prompt = prompts.CHECKPOINT_QUESTION_PROMPT.format(
            concept=state.current_concept,
            paper_title=self.engine.paper_title,
            recent_concepts=', '.join(recent),
            paper_context=self.engine.paper_context[:2000]
        )

        result = self.engine.call_claude_json(prompt)
        question = result.get('question', 'Explain what you just implemented and why it works.')

        state.phase = TutoringPhase.CHECKPOINT
        state.pending_checkpoint = question
        state.checkpoint_concept = result.get('concept_tested', state.current_concept)

        return TutoringResponse(
            message=f"**{prior_feedback}**\n\n"
                    f"Before we continue, let me check your understanding:\n\n"
                    f"**{question}**",
            waiting_for='answer',
            prompt_hint="Take your time to think through this..."
        )

    def _handle_checkpoint_response(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Evaluate checkpoint answer"""
        # Get key points for this checkpoint
        key_points_prompt = f"""What are the key points a student should mention when answering:
"{state.pending_checkpoint}"

About {state.checkpoint_concept} from "{self.engine.paper_title}"?

List 2-3 key points."""

        key_points = self.engine.call_claude(key_points_prompt, max_tokens=400)

        # Evaluate their answer
        prompt = prompts.EVALUATE_CHECKPOINT_PROMPT.format(
            concept=state.checkpoint_concept,
            question=state.pending_checkpoint,
            key_points=key_points,
            user_answer=user_input
        )

        result = self.engine.call_claude_json(prompt)

        passed = result.get('passed', False)
        feedback = result.get('feedback', '')

        if passed:
            state.metrics.record_checkpoint_result(True, state.checkpoint_concept)
            state.phase = TutoringPhase.SKELETON

            # Continue to next TODO
            if state.advance_todo():
                next_todo = state.get_current_todo()
                return TutoringResponse(
                    message=f"**Excellent!** {feedback}\n\n"
                            f"Let's continue. TODO {next_todo.id}: {next_todo.goal}",
                    waiting_for='code',
                    prompt_hint=f"Implement TODO {next_todo.id}..."
                )
            else:
                return self._show_completion_or_checkpoint(state)
        else:
            state.metrics.record_checkpoint_result(False, state.checkpoint_concept)
            missing = result.get('missing_points', [])
            review = result.get('review_suggestion', '')

            # Offer to explain or let them try again
            return TutoringResponse(
                message=f"{feedback}\n\n"
                        f"Missing: {', '.join(missing) if missing else 'See feedback above'}\n\n"
                        f"{review}\n\n"
                        f"Would you like me to explain this concept? (Type 'explain' or try answering again)",
                waiting_for='answer',
                prompt_hint="Try again or type 'explain'..."
            )

    def _show_completion_or_checkpoint(self, state: TutoringState) -> TutoringResponse:
        """Show completion message or final checkpoint"""
        state.mark_concept_complete()

        # Summary
        metrics = state.metrics
        summary = f"TODOs: {metrics.todos_first_try} first-try, {metrics.todos_needed_hints} with hints"

        # Check for mode suggestion
        suggestion = metrics.should_suggest_mode_change()
        mode_msg = ""
        if suggestion == 'challenge':
            mode_msg = "\n\nYou're doing great! Consider trying Challenge mode for the next concept."
        elif suggestion == 'guided':
            mode_msg = "\n\nWant a deeper explanation? Try Guided mode with 'mode guided'."

        return TutoringResponse(
            message=f"**Congratulations!** You've completed the implementation of {state.current_concept}!\n\n"
                    f"{summary}\n\n"
                    f"Use 'learn' to start another concept, or explore other commands.{mode_msg}",
            waiting_for='input',
            suggest_mode=suggestion
        )

    def _advance_to_next(self, state: TutoringState) -> TutoringResponse:
        """Handle 'next' command to advance after seeing solution"""
        todo = state.get_current_todo()
        if todo:
            todo.completed = True

        if state.advance_todo():
            next_todo = state.get_current_todo()
            state.metrics.current_hint_level = 0
            state.phase = TutoringPhase.SKELETON
            return TutoringResponse(
                message=f"Moving on to TODO {next_todo.id}: {next_todo.goal}",
                waiting_for='code',
                prompt_hint=f"Implement TODO {next_todo.id}..."
            )
        else:
            return self._show_completion_or_checkpoint(state)


class ChallengeModeHandler(BaseModeHandler):
    """
    Challenge Mode - User writes from scratch, Sherpa reviews.
    Good for testing understanding after Tutorial mode.
    """

    def start_concept(self, concept: str, state: TutoringState) -> TutoringResponse:
        """Present the challenge requirements"""
        state.phase = TutoringPhase.SKELETON  # Reusing phase for waiting for code

        # Generate requirements
        prompt = prompts.CHALLENGE_REQUIREMENTS_PROMPT.format(
            concept=concept,
            paper_title=self.engine.paper_title,
            paper_context=self.engine.paper_context[:3000]
        )

        result = self.engine.call_claude_json(prompt)

        if 'error' in result:
            return TutoringResponse.error("Failed to generate challenge. Try 'learn' again.")

        # Store requirements for later evaluation
        state.context = {
            'requirements': result.get('requirements', []),
            'constraints': result.get('constraints', []),
            'evaluation_criteria': result.get('evaluation_criteria', [])
        }

        requirements_text = '\n'.join(f"- {r}" for r in result.get('requirements', []))
        constraints_text = '\n'.join(f"- {c}" for c in result.get('constraints', []))

        state.awaiting_response = 'code'

        return TutoringResponse(
            message=f"**Challenge: {concept}**\n\n"
                    f"{result.get('description', '')}\n\n"
                    f"**Requirements:**\n{requirements_text}\n\n"
                    f"**Constraints:**\n{constraints_text}\n\n"
                    f"**Expected Input:** {result.get('inputs', 'See requirements')}\n"
                    f"**Expected Output:** {result.get('outputs', 'See requirements')}\n\n"
                    f"Write your complete implementation:",
            waiting_for='code',
            prompt_hint="Paste your implementation when ready..."
        )

    def handle(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Evaluate the user's complete implementation"""
        if state.phase == TutoringPhase.COMPLETE:
            return TutoringResponse(
                message="Challenge complete! Type 'learn' to try another.",
                waiting_for='input'
            )

        # Get reference approach
        ref_prompt = f"""What is the correct approach to implement {state.current_concept}?
Summarize the key steps and important details.

Paper: "{self.engine.paper_title}"
Context: {self.engine.paper_context[:2000]}"""

        reference = self.engine.call_claude(ref_prompt, max_tokens=800)

        # Evaluate submission
        prompt = prompts.EVALUATE_CHALLENGE_PROMPT.format(
            concept=state.current_concept,
            requirements='\n'.join(state.context.get('requirements', [])),
            constraints='\n'.join(state.context.get('constraints', [])),
            user_code=user_input,
            reference_approach=reference
        )

        result = self.engine.call_claude_json(prompt, max_tokens=1500)

        score = result.get('score', 'needs_work')
        strengths = '\n'.join(f"- {s}" for s in result.get('strengths', []))
        improvements = '\n'.join(f"- {i}" for i in result.get('improvements', []))

        state.phase = TutoringPhase.COMPLETE
        state.mark_concept_complete()

        score_emoji = {'excellent': '🌟', 'good': '✅', 'needs_work': '🔧', 'incomplete': '⚠️'}

        return TutoringResponse(
            message=f"**Challenge Review** {score_emoji.get(score, '')} {score.upper()}\n\n"
                    f"**What you did well:**\n{strengths or '- Good effort!'}\n\n"
                    f"**Areas for improvement:**\n{improvements or '- Keep practicing!'}\n\n"
                    f"**Detailed Feedback:**\n{result.get('detailed_feedback', '')}\n\n"
                    f"Type 'learn' to try another concept.",
            waiting_for='input'
        )


class DebugModeHandler(BaseModeHandler):
    """
    Debug Mode - Present buggy code for user to find and fix.
    Only suggested after demonstrating understanding.
    """

    def start_concept(self, concept: str, state: TutoringState) -> TutoringResponse:
        """Generate and present buggy code"""
        state.phase = TutoringPhase.SKELETON

        # Generate buggy code
        prompt = prompts.GENERATE_BUGGY_CODE_PROMPT.format(
            concept=concept,
            paper_title=self.engine.paper_title,
            paper_context=self.engine.paper_context[:3000]
        )

        result = self.engine.call_claude_json(prompt, max_tokens=2000)

        if 'error' in result:
            return TutoringResponse.error("Failed to generate debug challenge. Try 'learn' again.")

        # Store bugs for evaluation
        state.context = {
            'buggy_code': result.get('buggy_code', ''),
            'bugs': result.get('bugs', [])
        }

        bug_count = len(result.get('bugs', []))
        hint = result.get('hint_for_first_bug', '')

        state.awaiting_response = 'code'

        return TutoringResponse(
            message=f"**Debug Challenge: {concept}**\n\n"
                    f"This code has **{bug_count} bug{'s' if bug_count != 1 else ''}**. "
                    f"Find and fix them:\n\n"
                    f"```python\n{result.get('buggy_code', '')}\n```\n\n"
                    f"**Hint for the first bug:** {hint}\n\n"
                    f"Paste your fixed code:",
            waiting_for='code',
            prompt_hint="Find and fix the bugs..."
        )

    def handle(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """Evaluate user's bug fixes"""
        if state.phase == TutoringPhase.COMPLETE:
            return TutoringResponse(
                message="Debug challenge complete! Type 'learn' to try another.",
                waiting_for='input'
            )

        import json

        prompt = prompts.EVALUATE_DEBUG_SUBMISSION_PROMPT.format(
            concept=state.current_concept,
            buggy_code=state.context.get('buggy_code', ''),
            bugs_json=json.dumps(state.context.get('bugs', [])),
            user_code=user_input
        )

        result = self.engine.call_claude_json(prompt, max_tokens=1500)

        fixed = result.get('bugs_fixed', [])
        missed = result.get('bugs_missed', [])
        all_fixed = result.get('all_fixed', False)

        if all_fixed:
            state.phase = TutoringPhase.COMPLETE
            state.mark_concept_complete()
            state.metrics.record_todo_result(True, state.current_concept)

            return TutoringResponse(
                message=f"**All bugs fixed!** Great debugging skills!\n\n"
                        f"**Bugs you found:**\n" +
                        '\n'.join(f"- {b}" for b in fixed) + "\n\n"
                        f"{result.get('feedback', '')}\n\n"
                        f"Type 'learn' to try another concept.",
                waiting_for='input'
            )
        else:
            missed_text = '\n'.join(f"- {m}" for m in missed)
            new_bugs = result.get('new_bugs_introduced', [])
            new_bugs_text = '\n'.join(f"- {b}" for b in new_bugs) if new_bugs else ''

            return TutoringResponse(
                message=f"**Progress!** You fixed {len(fixed)} bug{'s' if len(fixed) != 1 else ''}, "
                        f"but {len(missed)} remain{'s' if len(missed) == 1 else ''}.\n\n"
                        f"**Still to fix:**\n{missed_text}\n\n"
                        + (f"**New issues introduced:**\n{new_bugs_text}\n\n" if new_bugs else "")
                        + f"{result.get('feedback', '')}\n\n"
                        f"Try again:",
                waiting_for='code',
                prompt_hint="Keep debugging..."
            )


class GuidedModeHandler(BaseModeHandler):
    """
    Guided Mode - Full explanations, no interaction required.
    Use when stuck or explicitly requested.
    """

    def start_concept(self, concept: str, state: TutoringState) -> TutoringResponse:
        """Provide comprehensive explanation"""
        state.phase = TutoringPhase.COMPLETE

        # Determine understanding level based on metrics
        metrics = state.metrics
        if metrics.todos_first_try + metrics.todos_needed_hints == 0:
            level = "beginner"
        elif metrics.success_rate() >= 0.7:
            level = "intermediate"
        else:
            level = "needs_reinforcement"

        prompt = prompts.GUIDED_EXPLANATION_PROMPT.format(
            concept=concept,
            paper_title=self.engine.paper_title,
            paper_context=self.engine.paper_context[:4000],
            understanding_level=level
        )

        # Stream the response for better UX (caller should handle streaming)
        explanation = self.engine.call_claude(prompt, max_tokens=3000)

        state.mark_concept_complete()

        return TutoringResponse(
            message=f"**{concept} - Full Explanation**\n\n{explanation}\n\n"
                    f"---\n\n"
                    f"Ready to try implementing? Switch to Tutorial mode with 'mode tutorial' and type 'learn'.",
            waiting_for='input'
        )

    def handle(self, user_input: str, state: TutoringState) -> TutoringResponse:
        """In guided mode, any input after explanation prompts for next action"""
        # Treat input as a follow-up question
        if len(user_input) > 10:  # Looks like a question
            prompt = f"""The student is learning {state.current_concept} from "{self.engine.paper_title}" and asks:

"{user_input}"

Paper context:
{self.engine.paper_context[:2000]}

Answer their question clearly and concisely."""

            answer = self.engine.call_claude(prompt, max_tokens=1000)

            return TutoringResponse(
                message=answer + "\n\nAnything else? Or type 'learn' to start a new topic.",
                waiting_for='input'
            )

        return TutoringResponse(
            message="Type 'learn' to explore another concept, 'mode tutorial' to try hands-on learning, "
                    "or ask a question about what we covered.",
            waiting_for='input'
        )
