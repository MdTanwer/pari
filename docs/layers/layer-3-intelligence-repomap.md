# Layer 3: Codebase Intelligence & Navigation

> **Design Principle**: *Start fast and simple; add AST intelligence as a fallback.*  
> **v1 Default Engine**: Substring ripgrep, regex searching, and path globbing (`find_files`, `grep_search`). Zero startup latency, zero parser warmup.  
> **v2 Advanced Fallback**: Tree-sitter AST Symbol Graph with Personalized PageRank (PPR), injected when ambiguous grep searches or enterprise codebases require structural call-graph awareness.

---

## 1. Overview: The Codebase Navigation Strategy

Effective code navigation balances **speed** and **semantic depth**:

### The v1 Foundation: High-Speed Substring Grep & Globbing (Default)
In the vast majority of everyday coding tasks, senior engineers do not need a multi-layer graph algorithm to locate code; they use fast regex search and file path globbing:
1. **`find_files(pattern)`**: Path globbing (e.g. `*auth*.py`, `src/**/*.ts`) to inspect repository hierarchy instantaneously.
2. **`grep_search(query, path_filter)`**: Ripgrep-powered substring and regex search across files with line numbers and bounding snippets.
3. **Key Advantages**: Zero startup indexing latency, zero memory overhead, 100% language-agnostic, and infallible on unparseable/broken syntax trees.

### The v2 Enhancement: Tree-sitter AST RepoMap (Configurable Fallback)
On enterprise codebases exceeding 50,000 LOC, blind grep loops can become inefficient when symbol names are ubiquitous (e.g. searching for `process()` returns 400 matches across 80 files).

For these scenarios, PARI v2 provides the **Tree-sitter AST RepoMap with Personalized PageRank (PPR)** as an advanced fallback (`--repomap=ppr`):
* Extracts class/function declarations and call sites via Tree-sitter grammars.
* Computes PageRank to pack the top 2,048 tokens of symbol signatures into Tier 3 of the prompt.
* Acts as a structural map when simple substring queries are ambiguous.

---

## 2. Six-Step v2 AST Pipeline Architecture (Fallback)


```
+-----------------------------------------------------------------------------------+
|                     SIX-STEP AST REPOMAP PIPELINE FLOW                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Repository Source Files]                                                        |
|         |                                                                         |
|         v                                                                         |
|  Step 1: Tree-sitter AST Symbol Extraction <---> [Worktree SQLite Cache]          |
|         |                                        (mtime + git HEAD invalidation)  |
|         v                                                                         |
|  Step 2: Weighted Bipartite Call Graph (FileA -> Symbol -> FileB)                |
|         |                                                                         |
|         v                                                                         |
|  Step 3: Personalized PageRank Computation (d = 0.85, active file bias)           |
|         |                                                                         |
|         v                                                                         |
|  Step 4: PARI Hub Suppression Filter (>50 inbound refs dampened by 0.05x)        |
|         |                                                                         |
|         v                                                                         |
|  Step 5: Binary Search Token Packing (TreeContext budget <= 2,048 tokens)         |
|         |                                                                         |
|         v                                                                         |
|  Step 6: Inject Structured RepoMap into Tier 3 Context Baseline                   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

### Step 1: Multi-Language Tree-sitter AST Symbol Extraction
For each source file in the repository:
* Parse source code into an Abstract Syntax Tree (AST) using compiled C bindings (`tree-sitter` and `tree-sitter-language-pack`).
* Execute language-specific `.scm` tag queries to classify tokens into two categories:
  * **`def` nodes**: Declarations of classes, functions, methods, interfaces, and exported constants.
  * **`ref` nodes**: Identifier references, call sites, type annotations, and import statements.
* Fallback: Pygments regex lexing for rare or bespoke domain-specific languages without tree-sitter grammars.

---

### Step 2: Bipartite Graph Construction & Edge Weighting
PARI models the entire codebase as a directed bipartite graph $G = (V, E)$ using NetworkX:

$$\text{File}_A \xrightarrow{\text{references}} \text{Symbol}_S \xrightarrow{\text{defined\_in}} \text{File}_B$$

```
   [File: controllers/auth.py]
              |
              | (references: 50x weight)
              v
     (Symbol: verify_jwt)
              |
              | (defined_in)
              v
    [File: security/crypto.py]
```

To prevent noise and prioritize semantic relevance, edge weights are adjusted via deterministic multipliers:
* **Active Working Files (Tier 5)**: $50\times$ multiplier (highest priority).
* **Identifiers in User Prompt**: $10\times$ multiplier.
* **High-Information Identifiers**: $10\times$ multiplier for snake_case/CamelCase tokens with length $\ge 8$ characters (e.g. `AuthenticationSessionManager`).
* **Trivial Identifiers**: $0.1\times$ dampening for underscore-prefixed tokens (`_helper`) or common short tokens (`id`, `data`).
* **Frequency Dampening**: Square-root dampening for high-frequency mentions:

$$W_{\text{effective}} = W_{\text{base}} \times \sqrt{N_{\text{refs}}}$$

---

### Step 3: Personalized PageRank (PPR) Formulation
Using the weighted adjacency matrix $M$, PARI computes the Personalized PageRank vector $p$:

$$p = (1 - d) v_{\text{active}} + d M p$$

Where:
* $d = 0.85$ (standard damping factor).
* $v_{\text{active}}$ is the personalization vector, concentrated on active working files and tokens explicitly referenced in the user's prompt.

The resulting vector gives every file and symbol in the repository a mathematically rigorous relevance score tailored directly to the task at hand.

---

### Step 4: PARI Hub Suppression Filter (Closing Aider F4)

**The Failure Mode in Aider**: Generic utility files (`utils.py`, `helpers.py`, `logger.py`, `types.ts`) receive hundreds of inbound references from across the repository. In standard PageRank, these utility sinks absorb immense weight, crowding out domain-critical classes from the context window.

**PARI's Architectural Solution**:
1. **Hub Classification**: Any source file possessing $> 50$ inbound references spanning $> 30\%$ of total repository files is classified as a **Utility Hub**.
2. **Hub Dampening**: Nodes classified as Utility Hubs receive a **$0.05\times$ penalty multiplier** in the personalization vector.
3. **Direct Query Override**: If the user prompt explicitly specifies a file name (e.g. `"update logger.py"`), that file receives an immediate **$200\times$ temporary override**, bypassing hub suppression entirely.

---

### Step 5: Binary Search Token Packing (2,048 Tokens)
Aider restricts its repo map to 1,024 tokens. On enterprise codebases, this budget truncates critical context. PARI allocates a precise **2,048-token budget** (doubled capacity, representing $<2\%$ of modern 128k/200k windows).

PARI utilizes `grep_ast.TreeContext` with binary search over the PageRank percentile threshold:
1. It identifies the optimal rank cutoff $T$ such that the formatted AST syntax fits precisely within 2,048 tokens.
2. It displays class and function signatures while pruning internal implementation bodies.
3. It retains line-number context, docstrings, and parameter type hints.

#### Example Output Injected into Context
```python
# src/security/crypto.py
class TokenManager:
    """Handles JWT generation, verification, and rotation."""

    def verify_jwt(self, raw_token: str) -> Claims: ...
    def refresh_session(self, refresh_token: str) -> TokenPair: ...


# src/controllers/auth.py
class AuthController:
    def handle_login(self, request: HttpRequest) -> HttpResponse: ...
```

---

### Step 6: Worktree-Scoped Durable Disk Cache (Closing Aider F6)

Parsing ASTs across a 100,000 LOC repository takes 500–800ms. Re-parsing on every prompt turn is unacceptable.

PARI implements a durable cache backed by `diskcache.Cache` at `.pari/tags.cache.v1`:
* **File `mtime` Invalidation**: Source files are only parsed when their filesystem modification timestamp changes.
* **Worktree-Scoped Keys**: Aider suffered from fatal SQLite database locks when developers used multiple git worktrees. PARI scopes cache keys by branch and commit:
  $$\text{CacheKey} = \text{hash}(\text{file\_path} + \text{mtime} + \text{git rev-parse HEAD})$$
  This isolates cache access per branch, preventing cross-worktree lock contention.

---

## 3. Performance & Impact Comparison

| Metric | PARI | Aider | Pi / OpenCode / Claude Code |
|---|---|---|---|
| **Turn-0 Codebase Awareness** | **Yes (PPR AST)** | Yes (PPR AST) | **No (0% awareness)** |
| **Exploratory Search Turns** | **0 turns** | 0 turns | 4 – 8 blind tool turns |
| **Token Budget** | **2,048 tokens** | 1,024 tokens | 0 tokens (Greps inline) |
| **Hub Distortion Mitigation** | **Yes (0.05x Filter)** | No (Utils dominate) | N/A |
| **Cross-Worktree SQLite Safety** | **Yes (Worktree scoped)**| No (`SQLITE_LOCKED`) | N/A |
| **Cache Warmup Time** | **< 40ms (cached)** | < 40ms (cached) | 0ms |
