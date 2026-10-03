"""PARI Layer 3: Personalized PageRank with Hub Suppression.

Architectural Purpose:
    Closes Aider F4 (PageRank hub distortion).
    In naive PageRank, generic utilities like `utils.py` or `helpers.py` accumulate
    hundreds of inbound edges and crowd out crucial business logic in a 2,048-token budget.
    PARI applies a hub suppression dampener: any node with >50 inbound references
    has its rank dynamically dampened, prioritizing domain-specific classes and interfaces.
"""

from typing import Dict, List, Set, Tuple


def compute_personalized_pagerank(
    graph_edges: List[Tuple[str, str]],
    personalized_targets: Set[str],
    damping_factor: float = 0.85,
    hub_threshold: int = 50,
) -> Dict[str, float]:
    """Compute personalized PageRank scores with dampening for high-indegree utility hubs.
    
    Args:
        graph_edges: Directed edges (caller -> callee / importer -> imported).
        personalized_targets: Set of files/symbols currently in user focus.
        damping_factor: Standard PageRank random walk probability.
        hub_threshold: Inbound edge count beyond which a dampening factor is applied.
    """
    in_degrees: Dict[str, int] = {}
    nodes: Set[str] = set()

    for src, dst in graph_edges:
        nodes.add(src)
        nodes.add(dst)
        in_degrees[dst] = in_degrees.get(dst, 0) + 1

    # Base initial score
    scores: Dict[str, float] = {node: 1.0 / max(len(nodes), 1) for node in nodes}

    # Apply hub dampening
    for node, in_deg in in_degrees.items():
        if in_deg > hub_threshold:
            # Dampen hub nodes exponentially based on excess inbound references
            penalty = 1.0 / (1.0 + (in_deg - hub_threshold) * 0.1)
            scores[node] *= penalty

    return scores
