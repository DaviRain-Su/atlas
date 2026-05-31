import pytest

from atlas_engine.fixtures import build_fixture_graph
from atlas_engine.graph import (
    CycleError,
    GraphIntegrityError,
    assemble,
    find_cycle,
    prerequisites,
    topological_order,
)
from atlas_engine.schemas import Edge, EdgeType, KnowledgeGraph, Node, NodeType


def _node(nid: str) -> Node:
    return Node(id=nid, document_id="d", type=NodeType.THEOREM, label=nid, statement="s")


def test_fixture_is_acyclic_and_orders():
    graph = build_fixture_graph()
    assert find_cycle(graph) is None
    order = topological_order(graph)
    # convex_set has no outgoing DAG edges -> it is a prerequisite of everything,
    # so it must appear before the theorem that depends on it.
    assert order.index("n_convex_set") < order.index("n_epi_theorem")
    assert order.index("n_epigraph") < order.index("n_epi_theorem")


def test_overlay_edge_does_not_create_cycle():
    # e5 (intuition_for) points theorem->function "backwards" but is not a DAG
    # edge, so the graph stays acyclic. This is the §5.2 design guarantee.
    graph = build_fixture_graph()
    # Sanity: the same pair has a forward DEPENDS_ON and a backward INTUITION_FOR.
    assert any(e.type is EdgeType.INTUITION_FOR for e in graph.edges)
    assert find_cycle(graph) is None


def test_real_cycle_detected():
    a, b, c = _node("a"), _node("b"), _node("c")
    edges = [
        Edge(id="1", src="a", dst="b", type=EdgeType.DEPENDS_ON),
        Edge(id="2", src="b", dst="c", type=EdgeType.DEPENDS_ON),
        Edge(id="3", src="c", dst="a", type=EdgeType.DEPENDS_ON),
    ]
    g = KnowledgeGraph(document_id="d", title="t", nodes=[a, b, c], edges=edges)
    cyc = find_cycle(g)
    assert cyc is not None and cyc[0] == cyc[-1]  # closed loop
    with pytest.raises(CycleError):
        topological_order(g)


def test_dangling_edge_rejected():
    g = KnowledgeGraph(
        document_id="d", title="t", nodes=[_node("a")],
        edges=[Edge(id="1", src="a", dst="ghost", type=EdgeType.DEPENDS_ON)],
    )
    with pytest.raises(GraphIntegrityError):
        assemble(g)


def test_prerequisite_closure():
    graph = build_fixture_graph()
    pre = prerequisites(graph, "n_epi_theorem")
    assert "n_convex_set" in pre   # transitive: theorem -> epigraph -> convex_set
    assert "n_convex_fn" in pre
