"""PARI Layer 1: Merkle DAG Session Graph.

Architectural Purpose:
    Harvested from Pi's session-manager.ts.
    Maintains session history as a Directed Acyclic Graph (DAG) using parentId references.
    Enables non-linear branching, checkpoints, and causal traversal without in-memory state loss.
"""

from typing import Dict, List, Optional
from pari.session.events import SessionEvent


class DAGNode:
    def __init__(self, event: SessionEvent):
        self.event = event
        self.parent: Optional["DAGNode"] = None
        self.children: List["DAGNode"] = []


class SessionDAG:
    """In-memory DAG index over the immutable session event stream."""

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.root_id: Optional[str] = None
        self.head_id: Optional[str] = None

    def add_event(self, event: SessionEvent) -> DAGNode:
        node = DAGNode(event)
        self.nodes[event.id] = node

        if event.parent_id and event.parent_id in self.nodes:
            parent_node = self.nodes[event.parent_id]
            node.parent = parent_node
            parent_node.children.append(node)
        elif self.root_id is None:
            self.root_id = event.id

        self.head_id = event.id
        return node

    def get_lineage(self, leaf_id: Optional[str] = None) -> List[SessionEvent]:
        """Traverse backwards from leaf to root to reconstruct the linear event thread."""
        current_id = leaf_id or self.head_id
        lineage: List[SessionEvent] = []

        while current_id and current_id in self.nodes:
            node = self.nodes[current_id]
            lineage.append(node.event)
            current_id = node.event.parent_id

        lineage.reverse()
        return lineage
