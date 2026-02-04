# Sherpa

<img src="https://github.com/user-attachments/assets/e21d5d03-4988-4b9a-bf4d-ee521ced3433" width="400" height="500">


**Your AI-powered guide to implementing ML papers.**

Sherpa is an interactive command-line tool that helps you learn and implement machine learning papers. Instead of just reading papers or copying code, Sherpa teaches you through scaffolded learning—guiding you step-by-step while you do the actual implementation.

## Features

- **Interactive Tutoring** — Four learning modes that adapt to your skill level
- **Smart Paper Search** — Find papers by intent (learn, implement, explore latest research)
- **Code Skeletons** — Structured TODOs that guide your implementation without giving away the answer
- **Checkpoint Questions** — Verify your understanding before moving forward
- **Hint Progression** — Three levels of hints when you're stuck
- **Session Memory** — Tracks your progress and adapts to your learning patterns

## Installation

```bash
# Clone the repository
git clone https://github.com/nikhilkuniyil/Sherpa.git
cd Sherpa

# Install dependencies
pip install -r requirements.txt

# Set up your API key (required for AI features)
python -m sherpa --setup
```

### Requirements

- Python 3.9+
- API key from any supported provider: Anthropic, OpenAI, or Google Gemini

## Quick Start

### Tutorial Mode (Recommended)

The easiest way to learn is **Tutorial Mode** — Sherpa generates a code skeleton with TODOs, and you fill them in using your favorite IDE:

```bash
# Start a tutorial on DPO
sherpa --mode tutorial "I want to implement DPO"

# Sherpa will:
# 1. Generate dpo_implementation.py with structured TODOs
# 2. Watch the file for changes
# 3. Automatically review your code when you save
```

Open the generated file in VS Code, Cursor, or any editor. Complete each TODO, save, and get instant feedback.

### Interactive REPL

For exploring papers and other learning modes:

```bash
# Start interactive mode
sherpa -i

# Or specify a tutoring mode
sherpa -i --mode tutorial    # Scaffolded learning (default)
sherpa -i --mode challenge   # Test yourself
sherpa -i --mode guided      # Full explanations
sherpa -i --mode debug       # Find and fix bugs
```

## CLI Reference

```bash
# File-based tutorial (recommended for learning)
sherpa --mode tutorial "I want to implement DPO"   # Creates file, watches for changes
sherpa --mode tutorial "teach me attention"        # Works with any ML concept

# Interactive mode
sherpa -i                              # Start REPL in tutorial mode
sherpa -i --mode challenge             # Start in challenge mode
sherpa --implement dpo_2023            # Load paper and start REPL

# Quick queries
sherpa "Should I implement DPO?"       # Ask about a paper
sherpa "I want to understand RLHF"     # Smart search with intent detection
sherpa --search "preference learning"  # Explicit search

# Learning paths
sherpa --path "learn DPO"              # Get recommended learning path
sherpa --path "RLHF" --expertise beginner

# Utilities
sherpa --list                          # List all papers in knowledge base
sherpa --setup                         # Configure API key
sherpa --mode-help                     # Explain tutoring modes
```

## REPL Commands

### Learning
| Command | Description |
|---------|-------------|
| `learn [concept]` | Start interactive learning session |
| `hint` | Get a hint (3 levels available) |
| `mode <name>` | Switch tutoring mode |

### Paper Discovery
| Command | Description |
|---------|-------------|
| `search <query>` | Smart search for papers |
| `search --latest <query>` | Find recent papers |
| `more` | Show more search results |
| `add <arxiv_id>` | Add paper from arXiv |
| `papers` | List papers in knowledge base |
| `recommend` | Get personalized recommendations |

### Paper Management
| Command | Description |
|---------|-------------|
| `load <paper_id>` | Load a paper |
| `fetch` | Download and parse PDF |
| `summary` | Show paper summary |

### Understanding
| Command | Description |
|---------|-------------|
| `explain <concept>` | Explain a concept from the paper |
| `equation <n>` | Show and explain an equation |
| `algorithm <n>` | Show algorithm pseudocode |
| `ask <question>` | Ask any question about the paper |

### Implementation
| Command | Description |
|---------|-------------|
| `start <path>` | Start implementation session |
| `plan` | Show implementation plan |
| `stage [n]` | Show current stage or jump to stage |
| `done` | Mark current stage complete |
| `progress` | Show implementation progress |

### Session
| Command | Description |
|---------|-------------|
| `resume [id]` | Resume a session |
| `sessions` | List all sessions |
| `status` | Show current session status |
| `save` | Save current session |

## Configuration

Sherpa stores configuration in `~/.sherpa/`:

```
~/.sherpa/
├── config.json      # API keys and settings
├── repl_history     # Command history
└── pdfs/            # Cached paper PDFs
```

### Supported LLM Providers

Sherpa supports multiple LLM providers:

| Provider | Models | Environment Variable |
|----------|--------|---------------------|
| **Anthropic** | Claude Sonnet 4 | `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT-4o | `OPENAI_API_KEY` |
| **Google** | Gemini 1.5 Pro | `GOOGLE_API_KEY` |

### Setting Up API Key

```bash
# Interactive setup (choose your provider)
sherpa --setup

# Or set environment variable directly
export ANTHROPIC_API_KEY=your-key-here   # Anthropic
export OPENAI_API_KEY=your-key-here      # OpenAI
export GOOGLE_API_KEY=your-key-here      # Google Gemini
```

The interactive setup lets you choose which provider to use and saves your preference.

## Available Papers

Sherpa comes with a curated knowledge base of post-training papers:

| Paper | Difficulty | Educational Value |
|-------|------------|-------------------|
| SFT Basics | Beginner | High |
| Reward Modeling | Beginner | High |
| RLHF (InstructGPT) | Intermediate | Very High |
| DPO | Intermediate | Very High |
| IPO | Intermediate | High |
| KTO | Intermediate | High |
| ORPO | Intermediate | High |
| SimPO | Advanced | High |
| RSO | Advanced | Medium |
| LIMA | Intermediate | Medium |

Add more papers from arXiv:
```
sherpa> add 2401.12345
```

## Development

### Running Tests

```bash
# Run all tests
python tests/run_all.py

# Run specific test suite
python -m tests.test_coach
python -m tests.test_tutoring
```

### Project Structure

```
sherpa/
├── cli.py              # Main CLI entry point
├── config.py           # Configuration management
├── llm.py              # Unified LLM client (Anthropic/OpenAI/Gemini)
├── db/                 # Knowledge base and sessions
│   ├── knowledge_base.py
│   ├── sessions.py
│   └── seed.py
├── engines/            # Recommendation and search engines
│   ├── agentic.py
│   ├── rule_based.py
│   └── smart_search.py
├── integrations/       # External integrations
│   ├── arxiv.py
│   └── claude_code.py
├── pdf/                # PDF parsing
│   ├── parser.py
│   └── extractor.py
├── repl/               # Interactive REPL
│   ├── session.py
│   └── commands.py
└── tutoring/           # Interactive tutoring system
    ├── engine.py       # Tutoring orchestrator
    ├── state.py        # State and metrics dataclasses
    ├── modes.py        # Mode handlers (Tutorial, Challenge, etc.)
    ├── skeleton.py     # Code skeleton generation
    ├── file_watcher.py # File watching for automatic review
    └── tutorial_runner.py  # File-based tutorial workflow
```

## How It Works

### File-Based Tutorial Workflow

When you run `sherpa --mode tutorial "topic"`, Sherpa creates an interactive learning experience:

1. **Generate Skeleton** — Sherpa creates a Python file (e.g., `dpo_implementation.py`) with:
   - Complete file structure with imports and class definitions
   - 4-7 numbered TODOs, each with a goal and hint
   - `pass` placeholders where your code goes

2. **Code in Your IDE** — Open the file in VS Code, Cursor, PyCharm, etc. Work through TODOs in order.

3. **Automatic Review** — When you save the file, Sherpa:
   - Detects which TODO you completed
   - Evaluates your implementation
   - Provides specific feedback (correct, incorrect, or needs improvement)
   - Guides you to the next TODO

4. **Completion** — Once all TODOs are done, Sherpa congratulates you and summarizes what you learned.

### Learning Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Tutorial** | Code skeletons with TODOs | Learning new concepts step-by-step |
| **Challenge** | Write from scratch, get feedback | Testing your understanding |
| **Guided** | Full explanations and walkthroughs | When you're completely new to a topic |
| **Debug** | Find and fix bugs in broken code | Deepening understanding through debugging |

### Adaptive Learning

Sherpa tracks your progress within a session:
- **Success rate** — How often you complete TODOs correctly on first try
- **Hint usage** — Whether you needed hints (3 levels available)
- **Concepts mastered** — Topics you've demonstrated understanding of

Based on your performance, Sherpa may suggest switching modes (e.g., "You're doing great! Try Challenge mode next time.")

## Contributing

Contributions are welcome! Areas where help is needed:

- Adding more papers to the knowledge base
- Improving pedagogical prompts
- Adding new tutoring techniques
- Supporting more paper sources beyond arXiv

## License

MIT License - see LICENSE file for details.

---

Built with Claude by Anthropic.
