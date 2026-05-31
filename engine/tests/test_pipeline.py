from atlas_engine.evals import evaluate
from atlas_engine.extract import FakeExtractor, merge_duplicate_nodes
from atlas_engine.fixtures import (
    DOC_ID,
    SOURCES,
    build_fixture_graph,
    build_gold_graph,
)
from atlas_engine.modality import Modality
from atlas_engine.pipeline import run_pipeline
from atlas_engine.schemas import Edge, EdgeType, KnowledgeGraph, Node, NodeType


def test_pipeline_runs_end_to_end_on_fixture():
    extractor = FakeExtractor(build_fixture_graph())
    result = run_pipeline(extractor, DOC_ID, "Convex (demo)", SOURCES)
    assert result.ok
    assert result.cycle is None
    assert len(result.graph.nodes) == 4
    assert result.verification.grounded_rate == 1.0
    assert result.learning_order  # non-empty topo order
    # modality reflects features: convex_set is spatial -> static diagram.
    assert result.modalities["n_convex_set"].modality is Modality.STATIC_DIAGRAM


def test_unverified_nodes_dropped_before_assembly():
    graph = build_fixture_graph()
    # Add a node whose citation quote is fabricated -> must be quarantined/dropped.
    graph.nodes.append(
        Node(
            id="n_bad", document_id=DOC_ID, type=NodeType.THEOREM,
            label="Theorem (bogus)", statement="not in book",
            citations=[],  # no provenance at all
        )
    )
    result = run_pipeline(FakeExtractor(graph), DOC_ID, "t", SOURCES)
    assert "n_bad" not in result.graph.node_ids()
    assert "n_bad" in result.verification.quarantined_nodes


def test_merge_duplicate_nodes_unions_and_repoints():
    n1 = Node(id="a1", document_id="d", type=NodeType.THEOREM, label="Pythagoras", statement="s")
    n2 = Node(id="a2", document_id="d", type=NodeType.THEOREM, label="pythagoras", statement="s")
    other = Node(id="b", document_id="d", type=NodeType.DEFINITION, label="Triangle", statement="s")
    edges = [Edge(id="e", src="b", dst="a2", type=EdgeType.DEPENDS_ON)]
    g = KnowledgeGraph(document_id="d", title="t", nodes=[n1, n2, other], edges=edges)
    merged = merge_duplicate_nodes(g)
    assert len(merged.nodes) == 2  # a1 and a2 collapse
    # the edge to a2 is repointed to the survivor a1
    assert merged.edges[0].dst == "a1"


def test_evals_perfect_against_identical_gold():
    extractor = FakeExtractor(build_fixture_graph())
    result = run_pipeline(extractor, DOC_ID, "Convex (demo)", SOURCES)
    report = evaluate(result, build_gold_graph())
    assert report.nodes.f1 == 1.0
    assert report.edges.f1 == 1.0
    assert report.grounded_rate == 1.0
    assert report.cycle_count == 0


def test_evals_penalize_missing_nodes():
    # Extractor misses one node -> recall < 1.
    partial = build_fixture_graph()
    gold = build_gold_graph()
    partial.nodes = partial.nodes[:-1]
    partial.edges = [e for e in partial.edges if "n_epi_theorem" not in (e.src, e.dst)]
    result = run_pipeline(FakeExtractor(partial), DOC_ID, "t", SOURCES)
    report = evaluate(result, gold)
    assert report.nodes.recall < 1.0
