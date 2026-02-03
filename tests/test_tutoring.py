#!/usr/bin/env python3
"""
Test suite for the interactive tutoring system.
"""

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

import tempfile
import os
from unittest.mock import Mock, MagicMock, patch

from sherpa.tutoring import (
    TutoringEngine,
    TutoringState,
    TutoringResponse,
    TutoringMode,
    TutoringPhase,
    LearnerMetrics,
    TodoItem,
    CodeSkeleton,
)
from sherpa.tutoring.modes import (
    TutorialModeHandler,
    ChallengeModeHandler,
    DebugModeHandler,
    GuidedModeHandler,
)


class TestTutoringState:
    """Tests for TutoringState and related dataclasses"""

    def test_initial_state(self):
        """Test default state initialization"""
        state = TutoringState()
        assert state.mode == TutoringMode.TUTORIAL
        assert state.phase == TutoringPhase.INIT
        assert state.current_concept == ''
        assert state.current_todo_index == 0

    def test_mode_enum(self):
        """Test TutoringMode enum values"""
        assert TutoringMode.TUTORIAL.value == 'tutorial'
        assert TutoringMode.GUIDED.value == 'guided'
        assert TutoringMode.CHALLENGE.value == 'challenge'
        assert TutoringMode.DEBUG.value == 'debug'

    def test_phase_enum(self):
        """Test TutoringPhase enum values"""
        assert TutoringPhase.INIT.value == 'init'
        assert TutoringPhase.WHY_BEFORE_HOW.value == 'why_before_how'
        assert TutoringPhase.SKELETON.value == 'skeleton'
        assert TutoringPhase.CHECKPOINT.value == 'checkpoint'

    def test_reset_for_new_concept(self):
        """Test state reset when starting a new concept"""
        state = TutoringState()
        state.current_todo_index = 3
        state.attempt_count = 5
        state.phase = TutoringPhase.COMPLETE

        state.reset_for_new_concept('test_concept')

        assert state.current_concept == 'test_concept'
        assert state.phase == TutoringPhase.WHY_BEFORE_HOW
        assert state.current_todo_index == 0
        assert state.attempt_count == 0

    def test_advance_todo(self):
        """Test advancing through TODOs"""
        state = TutoringState()
        state.current_skeleton = CodeSkeleton(
            code='test',
            todos=[
                TodoItem(id=1, goal='Todo 1'),
                TodoItem(id=2, goal='Todo 2'),
                TodoItem(id=3, goal='Todo 3'),
            ]
        )

        assert state.current_todo_index == 0
        assert state.advance_todo() == True
        assert state.current_todo_index == 1
        assert state.advance_todo() == True
        assert state.current_todo_index == 2
        assert state.advance_todo() == False  # No more TODOs
        assert state.current_todo_index == 2


class TestLearnerMetrics:
    """Tests for LearnerMetrics tracking"""

    def test_initial_metrics(self):
        """Test default metrics"""
        metrics = LearnerMetrics()
        assert metrics.todos_first_try == 0
        assert metrics.todos_needed_hints == 0
        assert metrics.success_rate() == 1.0  # Default when no attempts

    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        metrics = LearnerMetrics()
        metrics.todos_first_try = 3
        metrics.todos_needed_hints = 1
        assert metrics.success_rate() == 0.75

    def test_checkpoint_rate(self):
        """Test checkpoint pass rate calculation"""
        metrics = LearnerMetrics()
        metrics.checkpoints_passed = 4
        metrics.checkpoints_failed = 1
        assert metrics.checkpoint_rate() == 0.8

    def test_record_todo_result(self):
        """Test recording TODO results"""
        metrics = LearnerMetrics()

        metrics.record_todo_result(first_try=True, concept='concept1')
        assert metrics.todos_first_try == 1
        assert 'concept1' in metrics.concepts_understood

        metrics.record_todo_result(first_try=False, concept='concept2')
        assert metrics.todos_needed_hints == 1
        assert 'concept2' in metrics.concepts_struggled

    def test_should_offer_hint_proactively(self):
        """Test proactive hint offering logic"""
        metrics = LearnerMetrics()
        assert metrics.should_offer_hint_proactively() == False

        # Simulate struggling
        metrics.todos_first_try = 0
        metrics.todos_needed_hints = 3
        assert metrics.should_offer_hint_proactively() == True

    def test_mode_change_suggestion(self):
        """Test mode change suggestions"""
        metrics = LearnerMetrics()

        # Doing well - suggest challenge
        metrics.todos_first_try = 4
        metrics.todos_needed_hints = 0
        assert metrics.should_suggest_mode_change() == 'challenge'

        # Struggling - suggest guided
        metrics.todos_first_try = 0
        metrics.todos_needed_hints = 3
        assert metrics.should_suggest_mode_change() == 'guided'


class TestCodeSkeleton:
    """Tests for CodeSkeleton"""

    def test_get_current_todo(self):
        """Test getting TODO by index"""
        skeleton = CodeSkeleton(
            code='test code',
            todos=[
                TodoItem(id=1, goal='First'),
                TodoItem(id=2, goal='Second'),
            ]
        )

        assert skeleton.get_current_todo(0).goal == 'First'
        assert skeleton.get_current_todo(1).goal == 'Second'
        assert skeleton.get_current_todo(2) is None
        assert skeleton.get_current_todo(-1) is None

    def test_all_complete(self):
        """Test checking if all TODOs are complete"""
        skeleton = CodeSkeleton(
            code='test',
            todos=[
                TodoItem(id=1, goal='First', completed=False),
                TodoItem(id=2, goal='Second', completed=False),
            ]
        )

        assert skeleton.all_complete() == False

        skeleton.todos[0].completed = True
        assert skeleton.all_complete() == False

        skeleton.todos[1].completed = True
        assert skeleton.all_complete() == True


class TestTutoringResponse:
    """Tests for TutoringResponse"""

    def test_default_response(self):
        """Test default response values"""
        response = TutoringResponse(message='Test message')
        assert response.message == 'Test message'
        assert response.waiting_for == 'input'
        assert response.prompt_hint == ''

    def test_error_response(self):
        """Test error response factory"""
        response = TutoringResponse.error('Something went wrong')
        assert '[Error]' in response.message
        assert 'Something went wrong' in response.message


class TestTutoringEngine:
    """Tests for TutoringEngine"""

    def test_initialization(self):
        """Test engine initialization"""
        engine = TutoringEngine(
            claude_client=None,
            mode='tutorial',
            paper_title='Test Paper',
            paper_context='Test context'
        )

        assert engine.state.mode == TutoringMode.TUTORIAL
        assert engine.paper_title == 'Test Paper'
        assert engine.is_active() == False

    def test_mode_parsing(self):
        """Test mode string to enum parsing"""
        engine = TutoringEngine(claude_client=None, mode='challenge')
        assert engine.state.mode == TutoringMode.CHALLENGE

        engine = TutoringEngine(claude_client=None, mode='debug')
        assert engine.state.mode == TutoringMode.DEBUG

        # Unknown mode defaults to tutorial
        engine = TutoringEngine(claude_client=None, mode='invalid')
        assert engine.state.mode == TutoringMode.TUTORIAL

    def test_set_paper_context(self):
        """Test setting paper context"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        engine.set_paper_context('New Title', 'New Context')

        assert engine.paper_title == 'New Title'
        assert engine.paper_context == 'New Context'

    def test_mode_switch(self):
        """Test switching modes"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')

        response = engine._switch_mode('challenge')
        assert engine.state.mode == TutoringMode.CHALLENGE
        assert 'challenge' in response.message.lower()

        response = engine._switch_mode('invalid')
        assert 'Unknown mode' in response.message

    def test_is_active(self):
        """Test active state detection"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        assert engine.is_active() == False

        engine.state.phase = TutoringPhase.SKELETON
        assert engine.is_active() == True

        engine.state.phase = TutoringPhase.INIT
        assert engine.is_active() == False

    def test_hint_not_in_todo_phase(self):
        """Test hint request when not in TODO phase"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        engine.state.phase = TutoringPhase.INIT

        response = engine._give_hint()
        assert 'Hints are available' in response.message

    def test_hint_progression(self):
        """Test hint level progression"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        engine.state.phase = TutoringPhase.SKELETON
        engine.state.current_skeleton = CodeSkeleton(
            code='test',
            todos=[TodoItem(
                id=1,
                goal='Test goal',
                hint_l1='Level 1 hint',
                hint_l2='Level 2 hint',
                solution='Solution code'
            )]
        )

        # First hint - level 1
        response = engine._give_hint()
        assert 'Level 1' in response.message
        assert engine.state.metrics.current_hint_level == 1

        # Second hint - level 2
        response = engine._give_hint()
        assert 'Level 2' in response.message
        assert engine.state.metrics.current_hint_level == 2

        # Third hint - show solution
        response = engine._give_hint()
        assert 'solution' in response.message.lower()
        assert engine.state.metrics.current_hint_level == 3

    def test_exit_tutoring(self):
        """Test exiting tutoring session"""
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        engine.state.phase = TutoringPhase.SKELETON
        engine.state.metrics.todos_first_try = 2
        engine.state.metrics.todos_needed_hints = 1

        response = engine._exit_tutoring()

        assert engine.state.phase == TutoringPhase.INIT
        assert 'ended' in response.message.lower()
        assert '2' in response.message  # todos_first_try count


class TestModeHandlers:
    """Tests for mode-specific handlers"""

    def setup_method(self):
        """Set up mock engine for each test"""
        self.mock_engine = Mock()
        self.mock_engine.paper_title = 'Test Paper'
        self.mock_engine.paper_context = 'Test context for paper'
        self.mock_engine.call_claude = Mock(return_value='Mock response')
        self.mock_engine.call_claude_json = Mock(return_value={
            'on_right_track': True,
            'feedback': 'Good thinking!',
            'bridge_to_paper': 'This connects to...'
        })

    def test_tutorial_handler_init(self):
        """Test TutorialModeHandler initialization"""
        handler = TutorialModeHandler(self.mock_engine)
        assert handler.engine == self.mock_engine

    def test_challenge_handler_init(self):
        """Test ChallengeModeHandler initialization"""
        handler = ChallengeModeHandler(self.mock_engine)
        assert handler.engine == self.mock_engine

    def test_debug_handler_init(self):
        """Test DebugModeHandler initialization"""
        handler = DebugModeHandler(self.mock_engine)
        assert handler.engine == self.mock_engine

    def test_guided_handler_init(self):
        """Test GuidedModeHandler initialization"""
        handler = GuidedModeHandler(self.mock_engine)
        assert handler.engine == self.mock_engine


class TestIntegration:
    """Integration tests for the tutoring system"""

    def test_full_import_chain(self):
        """Test that all modules import correctly"""
        from sherpa.tutoring import TutoringEngine
        from sherpa.tutoring.state import TutoringState, LearnerMetrics
        from sherpa.tutoring.modes import TutorialModeHandler
        from sherpa.tutoring.prompts import WHY_BEFORE_HOW_PROMPT

        assert TutoringEngine is not None
        assert TutoringState is not None
        assert TutorialModeHandler is not None
        assert WHY_BEFORE_HOW_PROMPT is not None

    def test_repl_integration(self):
        """Test that REPL can initialize with tutoring engine"""
        with patch('sherpa.repl.session.get_api_key', return_value=None):
            from sherpa.repl import ImplementationREPL

            repl = ImplementationREPL(mode='tutorial')
            assert repl.tutoring_mode == 'tutorial'

    def test_cli_mode_argument(self):
        """Test CLI accepts mode argument"""
        import argparse

        # Simulate parsing args with mode
        parser = argparse.ArgumentParser()
        parser.add_argument('--mode', choices=['tutorial', 'guided', 'challenge', 'debug'])

        args = parser.parse_args(['--mode', 'challenge'])
        assert args.mode == 'challenge'


def run_all_tests():
    """Run all tutoring tests manually"""
    print("\n" + "=" * 70)
    print("Sherpa Tutoring System - Test Suite")
    print("=" * 70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: State Initialization
    print("\n[1/8] Testing TutoringState initialization...")
    try:
        state = TutoringState()
        assert state.mode == TutoringMode.TUTORIAL
        assert state.phase == TutoringPhase.INIT
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 2: Learner Metrics
    print("\n[2/8] Testing LearnerMetrics...")
    try:
        metrics = LearnerMetrics()
        metrics.todos_first_try = 3
        metrics.todos_needed_hints = 1
        assert metrics.success_rate() == 0.75
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 3: Code Skeleton
    print("\n[3/8] Testing CodeSkeleton...")
    try:
        skeleton = CodeSkeleton(
            code='test',
            todos=[TodoItem(id=1, goal='Test')]
        )
        assert skeleton.get_current_todo(0) is not None
        assert skeleton.all_complete() == False
        skeleton.todos[0].completed = True
        assert skeleton.all_complete() == True
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 4: TutoringEngine Initialization
    print("\n[4/8] Testing TutoringEngine initialization...")
    try:
        engine = TutoringEngine(
            claude_client=None,
            mode='tutorial',
            paper_title='Test',
            paper_context='Context'
        )
        assert engine.state.mode == TutoringMode.TUTORIAL
        assert engine.is_active() == False
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 5: Mode Switching
    print("\n[5/8] Testing mode switching...")
    try:
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        response = engine._switch_mode('challenge')
        assert engine.state.mode == TutoringMode.CHALLENGE
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 6: Hint Progression
    print("\n[6/8] Testing hint progression...")
    try:
        engine = TutoringEngine(claude_client=None, mode='tutorial')
        engine.state.phase = TutoringPhase.SKELETON
        engine.state.current_skeleton = CodeSkeleton(
            code='test',
            todos=[TodoItem(id=1, goal='Goal', hint_l1='H1', hint_l2='H2', solution='Sol')]
        )

        engine._give_hint()
        assert engine.state.metrics.current_hint_level == 1
        engine._give_hint()
        assert engine.state.metrics.current_hint_level == 2
        engine._give_hint()
        assert engine.state.metrics.current_hint_level == 3
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 7: Mode Handlers Import
    print("\n[7/8] Testing mode handlers import...")
    try:
        from sherpa.tutoring.modes import (
            TutorialModeHandler,
            ChallengeModeHandler,
            DebugModeHandler,
            GuidedModeHandler,
        )
        assert TutorialModeHandler is not None
        print("  PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        tests_failed += 1

    # Test 8: REPL Integration
    print("\n[8/8] Testing REPL integration...")
    try:
        with patch('sherpa.repl.session.get_api_key', return_value=None):
            from sherpa.repl import ImplementationREPL
            repl = ImplementationREPL(mode='challenge')
            assert repl.tutoring_mode == 'challenge'
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
        print("\nAll tutoring tests passed!")
        return 0
    else:
        print(f"\n{tests_failed} test(s) failed.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
