"""PARI Layer 3: Personalized PageRank with Hub Suppression.

Architectural Purpose:
    Closes Aider F4 (PageRank hub distortion).
    In naive PageRank, generic utilities like `utils.py` or `helpers.py` accumulate
    hundreds of inbound edges and crowd out crucial business logic in a 2,048-token
    budget.
    PARI applies a hub suppression dampener: any node with >50 inbound references
    has its rank dynamically dampened, prioritizing domain-specific classes and
    interfaces.
"""

_ITERATIONS = 40
_HUB_DAMPING = 0.05
_NAMED_HUB_BOOST = 200.0


def compute_personalized_pagerank(
    graph_edges: list[tuple[str, str]],
    personalized_targets: set[str],
    damping_factor: float = 0.85,
    hub_threshold: int = 50,
) -> dict[str, float]:
    """Rank nodes for this task. A hub the user named is not dampened.

    ``graph_edges`` are ``(source, destination)`` links. ``personalized_targets``
    are the files or symbols the prompt is about. Damping ``d`` is 0.85.
    """
    outgoing: dict[str, list[str]] = {}
    inbound_count: dict[str, int] = {}
    nodes: set[str] = set(personalized_targets)
    for source, destination in graph_edges:
        nodes.add(source)
        nodes.add(destination)
        outgoing.setdefault(source, []).append(destination)
        inbound_count[destination] = inbound_count.get(destination, 0) + 1
    if not nodes:
        return {}
    hubs = {node for node, count in inbound_count.items() if count > hub_threshold}
    personal = _personalization(nodes, personalized_targets, hubs)
    rank = dict(personal)
    for _ in range(_ITERATIONS):
        updated = {node: (1.0 - damping_factor) * personal[node] for node in nodes}
        for source, destinations in outgoing.items():
            share = damping_factor * rank.get(source, 0.0) / len(destinations)
            for destination in destinations:
                updated[destination] += share
        for hub in hubs:
            if hub not in personalized_targets:
                updated[hub] *= _HUB_DAMPING
        total = sum(updated.values()) or 1.0
        rank = {node: value / total for node, value in updated.items()}
    return rank


def _personalization(
    nodes: set[str], targets: set[str], hubs: set[str]
) -> dict[str, float]:
    weights = {node: 0.0 for node in nodes}
    if targets:
        for node in targets:
            if node in nodes:
                weights[node] = _NAMED_HUB_BOOST if node in hubs else 1.0
    if sum(weights.values()) == 0:
        weights = {node: 1.0 for node in nodes}
    total = sum(weights.values())
    return {node: value / total for node, value in weights.items()}
