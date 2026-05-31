"""Graph assembly + DAG acyclicity (ARCHITECTURE §4.5, §5.2).

Deductive books give us a free correctness signal: the learning-order DAG must
be acyclic. A cycle means the extractor got a direction wrong (e.g. swapped a
theorem and its corollary), so it is an automatic alarm — no human needed.

Pure stdlib (Kahn's algorithm); no networkx dependency for the core.
"""

from __future__ import annotations

from .schemas import Edge, KnowledgeGraph


class GraphIntegrityError(ValueError):
    """Raised when assembled edges reference unknown nodes."""


class CycleError(ValueError):
    """Raised when the learning-order DAG contains a cycle."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"learning-order DAG has a cycle: {' -> '.join(cycle)}")


def check_referential_integrity(graph: KnowledgeGraph) -> None:
    ids = graph.node_ids()
    for e in graph.edges:
        missing = {e.src, e.dst} - ids
        if missing:
            raise GraphIntegrityError(
                f"edge {e.id} references unknown node(s): {sorted(missing)}"
            )


def _dag_adjacency(graph: KnowledgeGraph) -> dict[str, list[str]]:
    """Raw dependency adjacency: src -> [dst] over DAG edges only.

    An edge means `src depends on dst` (dst is the prerequisite). Used to walk
    *toward* prerequisites. Overlay edges are excluded by design.
    """
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.dag_edges():
        adj[e.src].append(e.dst)
    return adj


def _learning_adjacency(graph: KnowledgeGraph) -> dict[str, list[str]]:
    """Reversed adjacency for learning order: prerequisite -> [dependent].

    All DAG edge types share the convention that `dst` is the prerequisite and
    `src` is what comes after it (see ARCHITECTURE §5.2). So a valid learning
    sequence — every prerequisite before the things that need it — is a
    topological sort of this reversed graph (dst -> src).
    """
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.dag_edges():
        adj[e.dst].append(e.src)
    return adj


def find_cycle(graph: KnowledgeGraph) -> list[str] | None:
    """Return one cycle (as a node path) over DAG edges, or None if acyclic."""
    adj = _dag_adjacency(graph)
    WHITE, GREY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in adj}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        color[u] = GREY
        stack.append(u)
        for v in adj[u]:
            if color[v] == GREY:  # back-edge -> cycle
                return stack[stack.index(v):] + [v]
            if color[v] == WHITE:
                found = dfs(v)
                if found:
                    return found
        color[u] = BLACK
        stack.pop()
        return None

    for nid in adj:
        if color[nid] == WHITE:
            found = dfs(nid)
            if found:
                return found
    return None


def topological_order(graph: KnowledgeGraph) -> list[str]:
    """Kahn's algorithm over DAG edges; raises CycleError if not acyclic.

    The order is a valid learning sequence: every prerequisite precedes the
    nodes that depend on it.
    """
    adj = _learning_adjacency(graph)
    indeg: dict[str, int] = {nid: 0 for nid in adj}
    for _, dsts in adj.items():
        for v in dsts:
            indeg[v] += 1

    # Deterministic tie-break by id keeps output stable for tests/snapshots.
    queue = sorted([nid for nid, d in indeg.items() if d == 0])
    order: list[str] = []
    while queue:
        u = queue.pop(0)
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
        queue.sort()

    if len(order) != len(adj):
        cycle = find_cycle(graph) or []
        raise CycleError(cycle)
    return order


def prerequisites(graph: KnowledgeGraph, node_id: str) -> set[str]:
    """Transitive prerequisite closure of `node_id` over DAG edges."""
    adj = _dag_adjacency(graph)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        u = stack.pop()
        for v in adj.get(u, []):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def assemble(graph: KnowledgeGraph) -> list[str]:
    """Validate integrity + acyclicity; return a valid learning order.

    This is the assembly gate from ARCHITECTURE §4.5: a graph that does not pass
    here is sent back to verification rather than persisted.
    """
    check_referential_integrity(graph)
    return topological_order(graph)
