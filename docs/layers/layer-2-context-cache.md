# Layer 2: Context and Cache Architecture

> **Closes Failures**: Claude Code F4 (KV cache invalidation billing cascades), Claude Code F7 (context amnesia on naive compaction), Cursor F3 (context drift).  
> **Harvested From**: OpenCode's Immutable Context Epochs, Pi's Autonomous Economic Cache Warmer, and Aider's 8-Tier ChatChunks hierarchy.

---

## 1. Overview & Economic Motivation

In modern frontier LLMs (such as Claude 3.7 Sonnet and GPT-4o), prompt caching provides substantial economic advantages:
* **Anthropic Cache Read**: $0.10\times$ baseline input cost ($0.375 / \text{M tokens}$).
* **Anthropic Cache Write**: $1.25\times$ baseline input cost ($3.75 / \text{M tokens}$).
* **Cache Miss Penalty**: Recomputing a 100k-token uncached prompt costs **10x more** than a cached read.

In naive architectures (such as Claude Code and Aider), a single line edit in an upstream file or a dynamic system prompt modification shifts all token prefixes. This invalidates 100% of the KV cache across all subsequent turns, triggering devastating billing spikes and higher turn latency.

PARI introduces an **Immutable Context Epoch Architecture** coupled with an **Autonomous Economic Cache Warmer** to guarantee 70–90% cost reductions across deep sessions.

---

## 2. The 8-Tier Context Epoch Hierarchy

PARI organizes context into an 8-tier hierarchical structure with three deterministic cache breakpoints:

```
PARI Context Epoch Structure:

+------------------------------------------------------+  <- IMMUTABLE BASELINE EPOCH
| Tier 1: System Identity & Core Behavioral Rules      |
| Tier 2: Tool Definitions & Canonical Schemas         |  [Cache Breakpoint 1]
| Tier 3: Repository Context (v1 File Manifest /       |
|         v2 Optional AST RepoMap when enabled)        |
| Tier 4: Readonly Reference Files (docs, interfaces)  |  [Cache Breakpoint 2]
+------------------------------------------------------+  <- STABILITY BOUNDARY
| Tier 5: Active Working Files (currently edited files)|  [Cache Breakpoint 3]
+------------------------------------------------------+  <- ACTIVE WORKING BOUNDARY
| Tier 6: Conversation Turn History (rolling transcript)
| Tier 7: Current Turn Input & Pending Tool Results    |  <- Dynamic Execution Region
| Tier 8: Strict Constraint & Anti-Hallucination Footer|
+------------------------------------------------------+
```

### Tier Definitions & Cache Breakpoints

1. **Tier 1 (System Identity)**: Core system instructions, safety bounds, persona, and output style invariants.
2. **Tier 2 (Tool Schemas)**: Exact JSON/tool schemas for `bash_exec`, `file_edit`, `read_tool_output`, `find_files`, and `grep_search`.
   * *Breakpoint 1*: Ensures tool schemas never incur cache-write overhead.
3. **Tier 3 (Repository Context)**:
   * *v1 Core (Default)*: High-level repository tree manifest (directory layout, key config files). Code navigation occurs dynamically via `find_files` and `grep_search` with zero parser delay.
   * *v2 Fallback (`--repomap=ppr`)*: Optional 2,048-token Tree-sitter AST symbol graph injected when structural call graph context is explicitly enabled.
4. **Tier 4 (Readonly Reference Files)**: Architecture specs, design docs, or reference headers explicitly loaded via `/add`.
   * *Breakpoint 2 (End of Immutable Baseline)*: Tiers 1–4 are assembled **once** at session start and frozen. They never change during a session unless a new session epoch is created.

5. **Tier 5 (Active Working Files)**: Content of files currently being modified by the agent.
   * *Breakpoint 3*: Changes as files are edited. When Tier 5 changes, only Tiers 5–8 recompute; **Tiers 1–4 remain 100% warm in cache**.
6. **Tier 6 (Conversation Turn History)**: Rolling transcript of user prompts, assistant plans, and concise tool execution confirmations.
7. **Tier 7 (Current Turn Input)**: The user's active prompt and the latest tool execution results.
8. **Tier 8 (Constraint Footer)**: Injected at the bottom of the prompt to counter model "recency bias", reiterating critical requirements (e.g. "Do not emit markdown outside tool calls").

---

## 3. Autonomous Economic Cache Warmer

Anthropic prompt caches possess a **5-minute (300-second) Time-To-Live (TTL)**. When a developer pauses to test code or read output, the cache expires, causing the next turn to incur a 1.25x full cache-write billing penalty.

PARI ports and adapts Pi's verified autonomous cache warmer into a native Python `asyncio` background task.

```
+-----------------------------------------------------------------------------------+
|                     AUTONOMOUS CACHE WARMER DECISION FLOW                         |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Agent Turn Completes] ---> [Start 270s Async Timer (90% of Anthropic TTL)]      |
|                                       |                                           |
|                                       v                                           |
|                       Is developer actively typing?                               |
|                         |                       |                                 |
|                       [YES]                    [NO]                               |
|                         |                       |                                 |
|                         v                       v                                 |
|                   [Reset Timer]       Timer reaches 270s                          |
|                                                 |                                 |
|                                                 v                                 |
|                                   Evaluate ROI Formula:                           |
|                                   E[Savings] = (P_cont * MissCost) - WarmCost     |
|                                                 |                                 |
|                                     +-----------+-----------+                     |
|                                     |                       |                     |
|                            [E[Savings] >= $0.05]   [E[Savings] < $0.05]           |
|                                     |                       |                     |
|                                     v                       v                     |
|                            [Send 1-token Ping]     [Allow TTL Expire Gracefully]  |
|                            (Reset TTL for 300s)                                   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### The Economic Decision Formula

PARI does not blindly ping models. It executes an autonomous economic cost-benefit evaluation at $90\%$ of TTL (270 seconds):

$$\mathbb{E}[\text{Savings}] = \Big(P_{\text{continuation}} \times \text{MissCost}\Big) - \text{WarmCost} \ge \$0.05$$

Where:
* $P_{\text{continuation}} = 0.15$ — Empirically measured probability that an idle developer resumes the session within the next TTL window.
* $\text{MissCost}$ — The financial penalty of writing the full context at $1.25\times$ pricing ($ContextSize \times \$3.75/\text{M}$).
* $\text{WarmCost}$ — The trivial cost of sending a 1-token output ping (`"ping"`) with cache read pricing ($ContextSize \times \$0.375/\text{M} + 1 \times \$15/\text{M}$).

#### Practical Cost Calculation Example (80k-Token Context)

* **Cache Miss Cost**: $80,000 \times \frac{\$3.75}{10^6} = \$0.30$
* **Expected Benefit**: $0.15 \times \$0.30 = \$0.045$
* **Warm Ping Cost**: $80,000 \times \frac{\$0.375}{10^6} + 1 \times \frac{\$15}{10^6} = \$0.030 + \$0.000015 = \$0.030$
* **Net Value**: If context exceeds **40,000 tokens**, maintaining cache warmth saves dollars per session while eliminating 3–5 seconds of prompt ingestion latency on the next turn.

---

## 4. Safe Context Compaction Engine

When the cumulative token count reaches **70% of the model's maximum context capacity**, PARI's Compaction Engine triggers automatically, closing Claude Code F7 (context amnesia) and Cursor F3 (context drift):

```
SAFE COMPACTION PROTOCOL:

[Context reaches 70% limit]
         |
         +---> NEVER compact Tiers 1–4 (Immutable Baseline stays 100% intact)
         +---> NEVER compact Tier 5 (Active working files remain complete)
         +---> NEVER compact across active tool calls (wait for completion)
         +---> PRESERVE the last 5 turns verbatim (maintains immediate cache)
         |
         v
[Compress Tiers 6 early turns into structured Markdown summary]
```

### Four Invariant Rules of Safe Compaction

1. **Tiers 1–5 are Inviolable**: System prompt, tool schemas, repo map, and active files are **never** summarized. The foundational mental model remains mathematically exact.
2. **Atomic Tool-Call Protection**: Compaction is strictly forbidden between a `TOOL_CALL` and its corresponding `TOOL_RESULT`. Compacting mid-tool execution causes state corruption.
3. **Preserve Immediate Recency**: The final 5 conversation turns are retained verbatim without summarization. This preserves immediate cache prefix locality.
4. **Structured Decision Summaries**: Early exploration turns are compressed into a structured summary capturing:
   * Hypotheses tested and discarded.
   * Architectural decisions agreed upon.
   * Key file paths and line offsets verified.

---

## 5. Architectural Comparison

| Feature | PARI | Claude Code | OpenCode | Aider |
|---|---|---|---|---|
| **Cache Breakpoint Strategy** | 3-Tier Boundary Isolated | 1 Heuristic Dynamic Point | Epoch Tiers | 3-Tier Prefix |
| **Upstream Edit Resilience** | Tiers 1–4 remain 100% warm | 100% Cache Miss ($10\times$ cost spike) | Partial | Partial |
| **Autonomous Cache Warmer** | Native Asyncio Economic ($E[\text{ROI}] \ge \$0.05$) | None | None | Synchronous Thread |
| **Compaction Strategy** | 4-Rule Invariant Protected | Indiscriminate single-pass | Rolling Epoch | Rolling Truncation |
| **Token Cost Savings** | **70% – 90%** | 30% – 50% | 50% – 70% | 40% – 60% |
