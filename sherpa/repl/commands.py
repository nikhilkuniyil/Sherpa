#!/usr/bin/env python3
"""
Command definitions for the implementation REPL.
"""

COMMANDS = {
    # Paper & Session Management
    'load': {
        'help': 'Load a paper by ID or arXiv ID',
        'usage': 'load <paper_id>',
        'examples': ['load dpo_2023', 'load 2305.18290'],
    },
    'fetch': {
        'help': 'Download and parse the paper PDF',
        'usage': 'fetch',
        'examples': ['fetch'],
    },
    'start': {
        'help': 'Start a new implementation session',
        'usage': 'start <project_path>',
        'examples': ['start ~/projects/my_dpo', 'start ./implementation'],
    },
    'resume': {
        'help': 'Resume an existing session',
        'usage': 'resume [session_id]',
        'examples': ['resume', 'resume abc123'],
    },
    'sessions': {
        'help': 'List all implementation sessions',
        'usage': 'sessions',
        'examples': ['sessions'],
    },
    'status': {
        'help': 'Show current session status',
        'usage': 'status',
        'examples': ['status'],
    },

    # Interactive Learning
    'learn': {
        'help': 'Start interactive learning session for the loaded paper',
        'usage': 'learn [concept]',
        'examples': ['learn', 'learn "DPO loss function"'],
    },
    'hint': {
        'help': 'Get a hint for the current TODO (3 levels of hints)',
        'usage': 'hint',
        'examples': ['hint'],
    },
    'mode': {
        'help': 'Switch tutoring mode (tutorial/guided/challenge/debug)',
        'usage': 'mode <mode_name>',
        'examples': ['mode tutorial', 'mode challenge', 'mode guided'],
    },

    # Understanding the paper
    'explain': {
        'help': 'Explain a concept from the paper',
        'usage': 'explain <concept>',
        'examples': ['explain "DPO loss"', 'explain Bradley-Terry'],
    },
    'equation': {
        'help': 'Show and explain an equation',
        'usage': 'equation <number>',
        'examples': ['equation 1', 'equation 3'],
    },
    'algorithm': {
        'help': 'Show algorithm pseudocode',
        'usage': 'algorithm <number>',
        'examples': ['algorithm 1'],
    },
    'ask': {
        'help': 'Ask a question about the paper',
        'usage': 'ask <question>',
        'examples': ['ask Why does DPO not need a reward model?'],
    },
    'summary': {
        'help': 'Show paper summary',
        'usage': 'summary',
        'examples': ['summary'],
    },

    # Implementation
    'plan': {
        'help': 'Show or generate implementation plan',
        'usage': 'plan',
        'examples': ['plan'],
    },
    'stage': {
        'help': 'Show current stage or jump to a stage',
        'usage': 'stage [number]',
        'examples': ['stage', 'stage 2'],
    },
    'implement': {
        'help': 'Invoke Claude Code to implement something',
        'usage': 'implement <description>',
        'examples': ['implement "the DPO loss function"', 'implement "data loader"'],
    },
    'code': {
        'help': 'Start Claude Code in interactive mode',
        'usage': 'code',
        'examples': ['code'],
    },
    'files': {
        'help': 'Show files created in this session',
        'usage': 'files',
        'examples': ['files'],
    },

    # Progress
    'done': {
        'help': 'Mark current stage as complete',
        'usage': 'done [notes]',
        'examples': ['done', 'done "Implemented basic loss function"'],
    },
    'skip': {
        'help': 'Skip current stage',
        'usage': 'skip [reason]',
        'examples': ['skip', 'skip "Already have this from another project"'],
    },
    'note': {
        'help': 'Add a note to current stage',
        'usage': 'note <text>',
        'examples': ['note "Need to revisit the gradient calculation"'],
    },
    'progress': {
        'help': 'Show implementation progress',
        'usage': 'progress',
        'examples': ['progress'],
    },

    # Discovery
    'search': {
        'help': 'Smart search for papers (finds foundational papers by default)',
        'usage': 'search <query> | search --latest <query>',
        'examples': [
            'search "direct preference optimization"',
            'search RLHF',
            'search --latest "preference learning 2024"'
        ],
    },
    'more': {
        'help': 'Show more papers from the last search (progressive disclosure)',
        'usage': 'more',
        'examples': ['more'],
    },
    'add': {
        'help': 'Add a paper from arXiv to knowledge base',
        'usage': 'add <arxiv_id>',
        'examples': ['add 2305.18290', 'add 2401.12345'],
    },
    'recommend': {
        'help': 'Get personalized paper recommendations',
        'usage': 'recommend [interest]',
        'examples': ['recommend', 'recommend "reinforcement learning for LLMs"'],
    },

    # Utilities
    'help': {
        'help': 'Show available commands',
        'usage': 'help [command]',
        'examples': ['help', 'help explain'],
    },
    'papers': {
        'help': 'List papers in knowledge base',
        'usage': 'papers',
        'examples': ['papers'],
    },
    'clear': {
        'help': 'Clear the screen',
        'usage': 'clear',
        'examples': ['clear'],
    },
    'save': {
        'help': 'Save current session',
        'usage': 'save',
        'examples': ['save'],
    },
    'exit': {
        'help': 'Exit the REPL',
        'usage': 'exit',
        'examples': ['exit', 'quit'],
    },
    'quit': {
        'help': 'Exit the REPL (alias for exit)',
        'usage': 'quit',
        'examples': ['quit'],
    },
}


def get_command_help(command: str = None) -> str:
    """Get help text for a command or all commands"""
    if command and command in COMMANDS:
        cmd = COMMANDS[command]
        lines = [
            f"  {command}: {cmd['help']}",
            f"  Usage: {cmd['usage']}",
        ]
        if cmd.get('examples'):
            lines.append(f"  Examples: {', '.join(cmd['examples'])}")
        return '\n'.join(lines)

    # Show all commands grouped
    groups = {
        'Learning': ['learn', 'hint', 'mode'],
        'Discovery': ['search', 'more', 'add', 'recommend', 'papers'],
        'Paper': ['load', 'fetch', 'summary'],
        'Session': ['start', 'resume', 'sessions', 'status', 'save'],
        'Understanding': ['explain', 'equation', 'algorithm', 'ask'],
        'Implementation': ['plan', 'stage', 'implement', 'code', 'files'],
        'Progress': ['done', 'skip', 'note', 'progress'],
        'Utilities': ['help', 'clear', 'exit'],
    }

    lines = ["Available commands:\n"]
    for group, cmds in groups.items():
        lines.append(f"  {group}:")
        for cmd in cmds:
            if cmd in COMMANDS:
                lines.append(f"    {cmd:12} - {COMMANDS[cmd]['help']}")
        lines.append("")

    lines.append("Type 'help <command>' for detailed help on a specific command.")
    return '\n'.join(lines)
