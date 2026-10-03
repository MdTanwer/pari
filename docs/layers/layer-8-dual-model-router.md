# Layer 8: Dual-Model Routing Engine

> **Closes Failures**: Antigravity F1 (200k–400k token planning burn), Aider F5 (reflection token exhaustion), and monolithic diff formatting waste.  
> **Harvested From**: Aider's ArchitectCoder / EditorCoder separation — enhanced with Dynamic Task Classification, Anti-Planning Guards, and Administrative Weak-Model Offloading.

---

## 1. The Core Rationale: Why Monolithic Agents Fail Economically

Monolithic agent architectures (such as standard Claude Code, Cursor, and Google Antigravity) route every turn through a single expensive frontier reasoning model (Claude 3.7 Sonnet Thinking, OpenAI o3, or DeepSeek R1). 

This introduces three critical systems engineering pathologies:

1. **The Mechanical Formatting Tax**: Frontier reasoning models charge premium prices ($15.00/M output tokens). Burning expensive reasoning tokens emitting 500 lines of repetitive `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` markers and JSON schema boilerplate is an economic disaster.
2. **Analysis Paralysis & Meta-Commentary Burn (Antigravity F1)**: Unconstrained reasoning models enter runaway self-reflection loops, generating 6–12 internal planning turns and burning 200k–400k tokens before editing a single line of code.
3. **Cognitive Contamination**: When a single model must simultaneously reason about high-level software architecture and emit character-exact whitespace-sensitive diffs, its attention budget is split, causing subtle off-by-one indentation errors.

**PARI's Architectural Solution**: Decouple **Architectural Reasoning** from **Deterministic File Mutation**.

---

## 2. Dual-Model Routing Architecture

```
USER PROMPT
     |
     v
TASK CLASSIFIER:
  - Scope Analysis: Estimated LOC touched, cross-file references
  - Complexity Signals: "architect", "refactor", "design", "how should"
  - Decision: Simple Edit (< 3 files) vs. Complex Architectural Plan
     |                                          |
     | [Complex Task]                           | [Simple Task: BYPASS]
     v                                          |
ARCHITECT MODEL                                 |
(Claude 3.7 Sonnet Thinking / o3)               |
  - Strict natural language plan only           |
  - Zero code formatting or diff syntax         |
  - Anti-Planning Ceiling: <= 4,096 tokens      |
     |                                          |
     +--------------------+---------------------+
                          |
                          v
                    EDITOR MODEL
       (Claude 3.5 Haiku / DeepSeek V3 / Flash)
         - Ingests plan + target files
         - Emits strict, character-exact SEARCH/REPLACE blocks
         - Executes atomic mutations to physical disk
```

---

## 3. The Economic Equation: 85% Cost Reduction

A common intuition is that issuing two API calls (Architect then Editor) must cost more than one. In token economics, **the exact opposite is true**:

### Monolithic Single-Model Call
* Input: 40k tokens context.
* Output: 400 tokens of reasoning + 3,500 tokens of mechanical diff code.
* Output Cost @ $15.00/M:
  $$\text{Cost} = 3,900 \times \frac{\$15.00}{10^6} = \mathbf{\$0.0585 \text{ per turn}}$$
* Over a typical 20-turn session: $\mathbf{\$1.17}$ in output tokens alone.

### PARI Dual-Model Routing
* **Step 1: Architect Call (Sonnet Thinking)**:
  * Ingests context; outputs a dense, high-signal 300-token architectural plan.
  * Cost @ $15.00/M:
    $$\text{Cost}_{\text{arch}} = 300 \times \frac{\$15.00}{10^6} = \mathbf{\$0.0045}$$
* **Step 2: Editor Call (Haiku / DeepSeek V3)**:
  * Ingests 300-token plan; outputs 3,500 tokens of mechanical diff blocks.
  * Cost @ $1.25/M:
    $$\text{Cost}_{\text{edit}} = 3,500 \times \frac{\$1.25}{10^6} = \mathbf{\$0.0043}$$
* **Total Output Cost per Turn**:
  $$\text{Total} = \$0.0045 + \$0.0043 = \mathbf{\$0.0088 \text{ per turn}}$$

$$\mathbf{85\% \text{ Net Cost Reduction}} \text{ with strictly superior code quality and zero indentation drift.}$$

---

## 4. Key Engine Guards

### 1. Anti-Planning Guard (Closing Antigravity F1)
To prevent recursive reasoning loops:
* A strict hard output token ceiling is enforced on the Architect model: `max_planning_tokens = 4096`.
* If the Architect fails to conclude its plan within 4k tokens, the output stream is cut.
* The partial plan is immediately handed to the Editor model with instructions: *"Execute the completed portion of this plan directly onto disk. Remainder tasks will be scheduled iteratively."*
* Completely arrests runaway meta-commentary loops.

---

### 2. Task Classifier Bypass (Zero Overhead on Simple Edits)
Not every turn requires an architectural plan:
* For localized edits ($< 3$ files touched, typo fixes, unit test assertion tweaks, CSS adjustments), the prompt bypasses the Architect entirely.
* The Editor model executes the edit directly in a single turn.
* Eliminates double-call latency on routine operations.

---

### 3. Weak Model Offloading for Administrative Tasks
Secondary operational chores are offloaded to ultra-cheap models (e.g. Gemini 2.5 Flash, Claude 3.5 Haiku, or DeepSeek V3):
* Synthesizing semantic Git commit messages from unified diffs.
* Summarizing truncated tool output sidecars.
* Generating session resumption summaries.
* Classifying incoming user prompts.

This preserves the primary frontier reasoning token budget exclusively for high-leverage architectural problem-solving.

---

## 5. Multi-Provider Model Mapping

PARI supports pluggable providers via a unified adapter interface:

| Role | Anthropic Profile | OpenAI Profile | Open-Weights / Local Profile |
|---|---|---|---|
| **Architect** | Claude 3.7 Sonnet (Thinking) | OpenAI o3 / o1 | DeepSeek R1 (671B) |
| **Editor** | Claude 3.5 Haiku | GPT-4o-mini | DeepSeek V3 / Qwen 2.5 Coder 32B |
| **Admin** | Claude 3.5 Haiku | GPT-4o-mini | Llama 3.3 70B (Ollama / vLLM) |
