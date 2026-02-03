#!/usr/bin/env python3
"""
Claude prompt templates for the interactive tutoring system.
"""

# =============================================================================
# WHY BEFORE HOW - Make user reason about approach before showing code
# =============================================================================

WHY_BEFORE_HOW_PROMPT = """You are a Socratic tutor teaching ML paper implementations. The student wants to learn about {concept} from the paper "{paper_title}".

Before showing ANY code, you must make the student reason about the approach first.

Paper context:
{paper_context}

Generate a "why before how" question that:
1. Sets up the problem context briefly (2-3 sentences)
2. Asks the student to think about HOW they would approach solving this problem
3. Does NOT give away the solution or mention specific techniques from the paper yet
4. Encourages the student to use their intuition

Example format:
"Before we write any code - let's think about the problem.

[Brief problem context]

Here's the question: [Thought-provoking question about the approach]"

Return ONLY the question text, no JSON or extra formatting."""


EVALUATE_WHY_RESPONSE_PROMPT = """You are evaluating a student's reasoning about how to approach {concept}.

The correct insight from the paper "{paper_title}" is:
{key_insight}

Student's response:
"{user_response}"

Evaluate their reasoning and provide feedback:
1. Acknowledge what they got right (be specific)
2. Gently correct any misconceptions
3. Bridge from their thinking to the actual approach used in the paper
4. Keep feedback to 3-4 sentences max

Return JSON:
{{
  "on_right_track": true/false,
  "feedback": "Your feedback here",
  "bridge_to_paper": "How this connects to the paper's approach"
}}"""


# =============================================================================
# PREDICT BEFORE REVEAL - Ask user what code does before explaining
# =============================================================================

PREDICT_CODE_PROMPT = """You are showing a key piece of code from {concept} and asking the student to predict what it does.

Code to show:
```python
{code_snippet}
```

Context from paper "{paper_title}":
{context}

Generate a question that:
1. Shows the code
2. Asks the student to break down what each part does
3. Does NOT explain it yet

Return ONLY the question text with the code block included."""


EVALUATE_PREDICTION_PROMPT = """You are evaluating a student's prediction about what code does.

Code shown:
```python
{code_snippet}
```

Correct explanation:
{correct_explanation}

Student's prediction:
"{user_prediction}"

Return JSON:
{{
  "understanding_level": "good|partial|needs_work",
  "feedback": "Specific feedback on their prediction",
  "explanation": "The full correct explanation (only if understanding_level is not 'good')"
}}"""


# =============================================================================
# SKELETON GENERATION - Create code skeletons with TODOs
# =============================================================================

SKELETON_GENERATION_PROMPT = """Generate a code skeleton for teaching {concept} from the paper "{paper_title}".

Paper context:
{paper_context}

Requirements:
1. Create a Python class/function skeleton with meaningful TODOs
2. Each TODO should:
   - Have a number (TODO 1, TODO 2, etc.)
   - Have a clear goal statement explaining WHAT to achieve (not just "implement this")
   - Be one logical step (5-15 lines of code when complete)
   - Build sequentially on the previous TODO
   - Have an implicit hint in the goal without giving away the implementation
3. Include 4-6 TODOs that cover the core implementation
4. Add brief context comments where they help understanding
5. Use realistic variable names and structure

Example TODO format in code:
```
# TODO 1: Store the policy model, reference model, and beta parameter
# Goal: Set up the two models - one trainable (policy), one frozen (reference)
pass
```

Return JSON:
{{
  "code": "the full skeleton code with TODO comments",
  "todos": [
    {{
      "id": 1,
      "goal": "Clear goal statement from the TODO comment",
      "hint_l1": "Conceptual hint - what to think about",
      "hint_l2": "More specific hint - what approach to use",
      "solution": "The correct implementation code"
    }},
    ...
  ],
  "concept_dependencies": ["list of prerequisite concepts the student should understand"]
}}"""


# =============================================================================
# TODO EVALUATION - Evaluate student's code submission for a TODO
# =============================================================================

EVALUATE_TODO_PROMPT = """You are evaluating a student's code submission for a TODO in an ML paper implementation exercise.

Context: Implementing {concept} from "{paper_title}"

TODO {todo_id}: {todo_goal}

Expected solution approach:
```python
{expected_solution}
```

Student's submission:
```python
{user_code}
```

Full skeleton for context:
```python
{skeleton_code}
```

Evaluate the submission:
1. Is it functionally correct for this TODO's goal?
2. Does it follow good practices?
3. Are there bugs, inefficiencies, or misunderstandings?

IMPORTANT:
- Be encouraging but honest
- Don't rewrite their code - give guidance
- If incorrect, identify the SPECIFIC issue
- Focus on the learning, not just correctness

Return JSON:
{{
  "correct": true/false,
  "feedback": "Specific, encouraging feedback",
  "issue_type": null | "bug" | "misunderstanding" | "incomplete" | "inefficient",
  "issue_detail": "If incorrect, what specifically is wrong",
  "hint_if_wrong": "A targeted hint without giving away the answer"
}}"""


# =============================================================================
# CHECKPOINT QUESTIONS - Verify understanding before advancing
# =============================================================================

CHECKPOINT_QUESTION_PROMPT = """Generate a checkpoint question to verify the student understands {concept} before moving on.

Paper: "{paper_title}"
Recently covered concepts: {recent_concepts}

Paper context:
{paper_context}

Requirements:
1. This should test REASONING, not recall
2. The question should require understanding WHY something works, not just WHAT it does
3. It should be answerable in 2-3 sentences
4. Avoid trivia like "what is the variable name for X"

Good examples:
- "Why do we need the reference model at all? What goes wrong without it?"
- "What happens to the loss if the policy assigns equal probability to chosen and rejected?"
- "Why do we use log probabilities instead of raw probabilities?"

Bad examples:
- "What is beta set to by default?"
- "How many parameters does the model have?"
- "What library do we use?"

Return JSON:
{{
  "question": "The checkpoint question",
  "key_points": ["Points a good answer should cover"],
  "concept_tested": "The specific concept being tested"
}}"""


EVALUATE_CHECKPOINT_PROMPT = """You are evaluating a student's answer to a checkpoint question about {concept}.

Question: "{question}"

Key points a good answer should include:
{key_points}

Student's answer:
"{user_answer}"

Evaluate:
1. Does the answer demonstrate understanding of the concept?
2. Did they hit the key points (doesn't need to be word-for-word)?
3. Are there any misconceptions?

Return JSON:
{{
  "passed": true/false,
  "feedback": "Encouraging, specific feedback",
  "missing_points": ["Any key points they missed"],
  "needs_review": true/false,
  "review_suggestion": "If needs_review, what to revisit"
}}"""


# =============================================================================
# CHALLENGE MODE - Generate requirements for from-scratch implementation
# =============================================================================

CHALLENGE_REQUIREMENTS_PROMPT = """Generate implementation requirements for a challenge exercise on {concept} from "{paper_title}".

Paper context:
{paper_context}

The student should implement this from scratch. Generate:
1. A clear description of what to implement
2. Specific constraints and requirements
3. Expected inputs and outputs
4. What NOT to use (to ensure they implement core logic themselves)

Return JSON:
{{
  "description": "What to implement (2-3 sentences)",
  "requirements": [
    "Specific requirement 1",
    "Specific requirement 2",
    ...
  ],
  "constraints": [
    "Constraint 1 (e.g., 'Do not use library X for Y')",
    ...
  ],
  "inputs": "Description of expected inputs",
  "outputs": "Description of expected outputs",
  "evaluation_criteria": ["What makes a good solution"]
}}"""


EVALUATE_CHALLENGE_PROMPT = """You are evaluating a student's from-scratch implementation of {concept}.

Requirements given:
{requirements}

Constraints:
{constraints}

Student's implementation:
```python
{user_code}
```

Reference implementation approach:
{reference_approach}

Evaluate comprehensively:
1. Does it meet the requirements?
2. Does it respect the constraints?
3. Is it functionally correct?
4. What's done well?
5. What could be improved?

Return JSON:
{{
  "meets_requirements": true/false,
  "respects_constraints": true/false,
  "functionally_correct": true/false,
  "score": "excellent|good|needs_work|incomplete",
  "strengths": ["What they did well"],
  "improvements": ["What could be better"],
  "detailed_feedback": "Comprehensive feedback paragraph"
}}"""


# =============================================================================
# DEBUG MODE - Generate buggy code for debugging exercises
# =============================================================================

GENERATE_BUGGY_CODE_PROMPT = """Generate buggy code for a debugging exercise on {concept} from "{paper_title}".

Paper context:
{paper_context}

Create code that:
1. Looks mostly correct at first glance
2. Has 2-3 realistic bugs that students commonly make
3. Bugs should be conceptual or subtle, not obvious syntax errors

Bug types to include (pick 2-3):
- Off-by-one errors in tensor dimensions
- Missing gradient detach on reference model
- Wrong sign in loss function
- Incorrect masking (e.g., padding handled wrong)
- Broadcasting issues
- Wrong reduction (mean vs sum)
- Missing normalization

Return JSON:
{{
  "buggy_code": "The code with bugs",
  "bugs": [
    {{
      "location": "Line number or description",
      "bug_type": "Category of bug",
      "description": "What's wrong",
      "fix": "The correct code"
    }},
    ...
  ],
  "hint_for_first_bug": "A subtle hint for the first bug"
}}"""


EVALUATE_DEBUG_SUBMISSION_PROMPT = """You are evaluating a student's attempt to fix buggy code for {concept}.

Original buggy code:
```python
{buggy_code}
```

Known bugs:
{bugs_json}

Student's fixed code:
```python
{user_code}
```

Evaluate:
1. Which bugs did they find and fix correctly?
2. Which bugs did they miss?
3. Did they introduce any new bugs?
4. Did they make unnecessary changes?

Return JSON:
{{
  "bugs_fixed": ["List of bugs they fixed correctly"],
  "bugs_missed": ["List of bugs they missed"],
  "new_bugs_introduced": ["Any new bugs they added"],
  "unnecessary_changes": ["Changes that weren't needed"],
  "feedback": "Overall feedback",
  "all_fixed": true/false
}}"""


# =============================================================================
# GUIDED MODE - Full explanation prompts
# =============================================================================

GUIDED_EXPLANATION_PROMPT = """Provide a comprehensive explanation of {concept} from "{paper_title}" for a student learning to implement it.

Paper context:
{paper_context}

Student's current understanding level: {understanding_level}

Provide:
1. Clear conceptual explanation (why this approach works)
2. Step-by-step breakdown of the implementation
3. Key code with inline explanations
4. Common pitfalls to avoid
5. Connection to the paper's broader contribution

Format with markdown for readability. Use code blocks for examples.
Be thorough but not overwhelming - aim for clarity over completeness."""


# =============================================================================
# ADAPTIVE PROMPTS - Based on learner metrics
# =============================================================================

REVIEW_SUGGESTION_PROMPT = """The student has been struggling with {struggled_concepts}.

They are now working on {current_concept}.

Given this context from the paper "{paper_title}":
{paper_context}

Generate a brief (2-3 sentence) suggestion that:
1. Acknowledges they might want to review something
2. Explains how the struggled concept connects to current work
3. Offers to help review if they want

Keep it supportive, not discouraging."""


MODE_SWITCH_SUGGESTION_PROMPT = """Based on the student's performance:
- TODOs correct first try: {todos_first_try}
- TODOs needing hints: {todos_needed_hints}
- Success rate: {success_rate}

Current mode: {current_mode}
Suggested mode: {suggested_mode}

Generate a brief (2-3 sentence) suggestion that:
1. Acknowledges their performance (positively!)
2. Suggests trying a different mode
3. Explains why that mode might be good for them now

Don't be condescending. Make it feel like a natural progression."""
