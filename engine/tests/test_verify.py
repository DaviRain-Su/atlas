from atlas_engine.fixtures import SOURCES, build_fixture_graph
from atlas_engine.schemas import (
    Citation,
    Entailment,
    KnowledgeGraph,
    Node,
    NodeType,
)
from atlas_engine.verify import quote_matches, verify_graph


def test_fixture_quotes_are_all_exact():
    graph = build_fixture_graph()
    for node in graph.nodes:
        for c in node.citations:
            assert quote_matches(c, SOURCES), f"bad quote on {node.id}"


def test_fabricated_quote_is_caught():
    # A citation whose quote is not the real substring must fail the gate.
    bad = Node(
        id="fake",
        document_id="convex-demo",
        type=NodeType.THEOREM,
        label="Theorem (Hallucinated)",
        statement="Something the book never says.",
        citations=[
            Citation(
                document_id="convex-demo", page_no=1,
                char_start=0, char_end=20,
                quote="THIS IS NOT IN BOOK!",  # wrong text at that span
                entailment=Entailment.YES, confidence=0.99,
            )
        ],
    )
    graph = KnowledgeGraph(document_id="convex-demo", title="t", nodes=[bad], edges=[])
    report = verify_graph(graph, SOURCES)
    assert bad.verified is False
    assert "fake" in report.quarantined_nodes
    assert "node:fake" in report.bad_quotes


def test_entailment_no_is_not_grounded():
    text = SOURCES[("convex-demo", 1)]
    needle = "A set C is convex"
    start = text.index(needle)
    n = Node(
        id="n", document_id="convex-demo", type=NodeType.DEFINITION,
        label="d", statement="s",
        citations=[
            Citation(
                document_id="convex-demo", page_no=1,
                char_start=start, char_end=start + len(needle),
                quote=needle, entailment=Entailment.NO, confidence=0.9,
            )
        ],
    )
    g = KnowledgeGraph(document_id="convex-demo", title="t", nodes=[n], edges=[])
    verify_graph(g, SOURCES)
    assert n.verified is False  # exact quote, but entailment=NO -> not grounded


def test_grounded_rate_on_fixture_is_one():
    graph = build_fixture_graph()
    report = verify_graph(graph, SOURCES)
    assert report.grounded_rate == 1.0
    assert not report.bad_quotes
