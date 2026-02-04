#!/usr/bin/env python3
"""
Interactive tutoring system for ML paper implementation coaching.

Supports four modes:
- Tutorial (default): Scaffolded learning with code skeletons (file-based)
- Guided: Full explanations for when you're stuck
- Challenge: Write from scratch, get feedback
- Debug: Find and fix bugs in broken code
"""

from .state import (
    TutoringMode,
    TutoringPhase,
    TutoringState,
    TutoringResponse,
    LearnerMetrics,
    TodoItem,
    CodeSkeleton,
)
from .engine import TutoringEngine
from .skeleton import SkeletonGenerator
from .file_watcher import FileWatcher, TutorialSession
from .tutorial_runner import TutorialRunner, run_tutorial

__all__ = [
    'TutoringMode',
    'TutoringPhase',
    'TutoringState',
    'TutoringResponse',
    'LearnerMetrics',
    'TodoItem',
    'CodeSkeleton',
    'TutoringEngine',
    'SkeletonGenerator',
    'FileWatcher',
    'TutorialSession',
    'TutorialRunner',
    'run_tutorial',
]
