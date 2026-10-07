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
        # TODO: Initialize node map and head/root pointers
        pass

    def add_event(self, event: SessionEvent) -> DAGNode:
        """Insert event into DAG and link parent/child pointers."""
        raise NotImplementedError

    def get_lineage(self, leaf_id: str | None = None) -> list[SessionEvent]:
        """Traverse backwards from leaf to root to reconstruct the linear event
        thread."""
        raise NotImplementedError
