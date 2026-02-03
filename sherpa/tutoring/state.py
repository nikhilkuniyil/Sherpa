#!/usr/bin/env python3
"""
State management for the interactive tutoring system.
Tracks tutoring phase, learner metrics, and session context.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class TutoringMode(Enum):
    """Available tutoring modes"""
    TUTORIAL = 'tutorial'    # Scaffolded learning with code skeletons (DEFAULT)
    GUIDED = 'guided'        # Full explanations, no interaction required
    CHALLENGE = 'challenge'  # Requirements only, user writes from scratch
    DEBUG = 'debug'          # Buggy code, user finds and fixes issues


class TutoringPhase(Enum):
    """Phases within a tutoring session"""
    INIT = 'init'                      # Not started
    WHY_BEFORE_HOW = 'why_before_how'  # Asking user to reason about approach
    PREDICT = 'predict'                 # Asking user to predict what code does
    SKELETON = 'skeleton'               # Showing skeleton, waiting for TODO
    TODO_REVIEW = 'todo_review'         # Evaluating user's TODO submission
    CHECKPOINT = 'checkpoint'           # Asking checkpoint question
    FEEDBACK = 'feedback'               # Providing feedback on submission
    COMPLETE = 'complete'               # Concept/session complete


@dataclass
class TodoItem:
    """A single TODO in a code skeleton"""
    id: int
    goal: str                    # Clear goal statement
    hint_l1: str = ''           # Conceptual nudge
    hint_l2: str = ''           # More specific direction
    solution: str = ''          # Full solution (only shown after hint_l2)
    completed: bool = False
    attempts: int = 0
    hints_given: int = 0


@dataclass
class CodeSkeleton:
    """Generated code skeleton with TODOs"""
    code: str                            # The skeleton code with TODO comments
    todos: List[TodoItem] = field(default_factory=list)
    concept: str = ''                    # What concept this teaches
    dependencies: List[str] = field(default_factory=list)  # Prerequisite concepts

    def get_current_todo(self, index: int) -> Optional[TodoItem]:
        """Get TODO at the specified index"""
        if 0 <= index < len(self.todos):
            return self.todos[index]
        return None

    def all_complete(self) -> bool:
        """Check if all TODOs are completed"""
        return all(todo.completed for todo in self.todos)


@dataclass
class LearnerMetrics:
    """Tracks user performance for adaptive tutoring"""
    # Concept tracking
    concepts_understood: List[str] = field(default_factory=list)
    concepts_struggled: List[str] = field(default_factory=list)

    # TODO performance
    todos_first_try: int = 0          # TODOs correct on first attempt
    todos_needed_hints: int = 0       # TODOs that required hints

    # Checkpoint performance
    checkpoints_passed: int = 0
    checkpoints_failed: int = 0

    # Current session hints
    current_hint_level: int = 0       # 0=none, 1=conceptual, 2=specific, 3=full

    def success_rate(self) -> float:
        """Calculate overall success rate"""
        total = self.todos_first_try + self.todos_needed_hints
        return self.todos_first_try / total if total > 0 else 1.0

    def checkpoint_rate(self) -> float:
        """Calculate checkpoint pass rate"""
        total = self.checkpoints_passed + self.checkpoints_failed
        return self.checkpoints_passed / total if total > 0 else 1.0

    def should_offer_hint_proactively(self) -> bool:
        """Determine if we should proactively offer hints based on performance"""
        # If user has been struggling, be more proactive with hints
        if self.success_rate() < 0.5 and (self.todos_first_try + self.todos_needed_hints) >= 2:
            return True
        return False

    def should_suggest_mode_change(self) -> Optional[str]:
        """Suggest a mode change based on performance"""
        total_todos = self.todos_first_try + self.todos_needed_hints

        # If doing really well in tutorial, suggest challenge
        if total_todos >= 3 and self.success_rate() >= 0.8:
            return 'challenge'

        # If struggling a lot, suggest guided for current concept
        if total_todos >= 2 and self.success_rate() < 0.3:
            return 'guided'

        return None

    def record_todo_result(self, first_try: bool, concept: str = ''):
        """Record the result of a TODO attempt"""
        if first_try:
            self.todos_first_try += 1
            if concept and concept not in self.concepts_understood:
                self.concepts_understood.append(concept)
        else:
            self.todos_needed_hints += 1
            if concept and concept not in self.concepts_struggled:
                self.concepts_struggled.append(concept)

    def record_checkpoint_result(self, passed: bool, concept: str = ''):
        """Record the result of a checkpoint question"""
        if passed:
            self.checkpoints_passed += 1
        else:
            self.checkpoints_failed += 1
            if concept and concept not in self.concepts_struggled:
                self.concepts_struggled.append(concept)


@dataclass
class TutoringState:
    """Current state of the tutoring session"""
    # Mode and phase
    mode: TutoringMode = TutoringMode.TUTORIAL
    phase: TutoringPhase = TutoringPhase.INIT

    # Current learning unit
    current_concept: str = ''
    current_skeleton: Optional[CodeSkeleton] = None
    current_todo_index: int = 0
    pending_checkpoint: Optional[str] = None
    checkpoint_concept: str = ''  # Concept being tested by checkpoint

    # User submission tracking
    user_code_attempt: str = ''
    attempt_count: int = 0

    # Conversation context flags
    why_question_asked: bool = False
    predict_question_asked: bool = False
    awaiting_response: str = ''  # What type of response we're waiting for

    # Learning progress
    completed_concepts: List[str] = field(default_factory=list)
    concepts_to_review: List[str] = field(default_factory=list)

    # Metrics
    metrics: LearnerMetrics = field(default_factory=LearnerMetrics)

    def reset_for_new_concept(self, concept: str):
        """Reset state for learning a new concept"""
        self.current_concept = concept
        self.phase = TutoringPhase.WHY_BEFORE_HOW
        self.current_skeleton = None
        self.current_todo_index = 0
        self.pending_checkpoint = None
        self.checkpoint_concept = ''
        self.user_code_attempt = ''
        self.attempt_count = 0
        self.why_question_asked = False
        self.predict_question_asked = False
        self.awaiting_response = ''
        self.metrics.current_hint_level = 0

    def get_current_todo(self) -> Optional[TodoItem]:
        """Get the current TODO item"""
        if self.current_skeleton:
            return self.current_skeleton.get_current_todo(self.current_todo_index)
        return None

    def advance_todo(self) -> bool:
        """Move to the next TODO. Returns False if no more TODOs."""
        if self.current_skeleton:
            if self.current_todo_index < len(self.current_skeleton.todos) - 1:
                self.current_todo_index += 1
                self.attempt_count = 0
                self.metrics.current_hint_level = 0
                return True
        return False

    def mark_concept_complete(self):
        """Mark current concept as completed"""
        if self.current_concept and self.current_concept not in self.completed_concepts:
            self.completed_concepts.append(self.current_concept)
        self.phase = TutoringPhase.COMPLETE

    def needs_review(self, concept: str):
        """Mark a concept as needing review"""
        if concept not in self.concepts_to_review:
            self.concepts_to_review.append(concept)


@dataclass
class TutoringResponse:
    """Response from the tutoring engine to display to user"""
    message: str                         # Main message to display
    waiting_for: str = 'input'           # input|code|reasoning|answer
    prompt_hint: str = ''                # Hint shown in prompt area
    show_progress: bool = False          # Whether to show progress indicator
    progress_info: Dict = field(default_factory=dict)  # Progress details
    suggest_mode: Optional[str] = None   # Suggested mode change
    suggest_review: Optional[str] = None # Concept to review

    @classmethod
    def error(cls, message: str) -> 'TutoringResponse':
        """Create an error response"""
        return cls(message=f"[Error] {message}", waiting_for='input')
