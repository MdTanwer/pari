"""PARI Layer 1: Merkle DAG Session Graph.

Architectural Purpose:
    Harvested from Pi's session-manager.ts.
    Maintains session history as a Directed Acyclic Graph (DAG) using parentId
    references.
    Enables non-linear branching, checkpoints, and causal traversal without in-memory
    state loss.
"""

from pari.session.events import SessionEvent


class DAGNode:
    """Represents a node in the causal event Merkle DAG."""

    def __init__(self, event: SessionEvent):
        self.event = event
        self.parent: DAGNode | None = None
        self.children: list[DAGNode] = []


class SessionDAG:
    """In-memory DAG index over the immutable session event stream."""

    def __init__(self):
        self._nodes: dict[str, DAGNode] = {}
        self.head: DAGNode | None = None

    def add_event(self, event: SessionEvent) -> DAGNode:
        """Insert event into DAG and link parent/child pointers."""
        if event.id is None:
            raise ValueError("Session event is missing an id.")
        node = DAGNode(event)
        self._nodes[event.id] = node
        if event.parent_id is not None:
            parent = self._nodes.get(event.parent_id)
            if parent is not None:
                node.parent = parent
                parent.children.append(node)
        self.head = node
        return node

    def get_lineage(self, leaf_id: str | None = None) -> list[SessionEvent]:
        """Traverse backwards from leaf to root to reconstruct the linear event
        thread."""
        if leaf_id is None:
            node = self.head
        else:
            node = self._nodes[leaf_id]
        chain: list[SessionEvent] = []
        while node is not None:
            chain.append(node.event)
            node = node.parent
        chain.reverse()
        return chain
