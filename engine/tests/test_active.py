from atlas_engine.active import build_recall_item, generate_recall_items
from atlas_engine.fixtures import SOURCES, build_fixture_graph
from atlas_engine.schemas import Node, NodeType
from atlas_engine.verify import verify_graph


def _node(t: NodeType) -> Node:
    return Node(id="x", document_id="d", type=t, label="L", statement="alpha bravo charlie")


def test_kind_chosen_by_node_type():
    assert build_recall_item(_node(NodeType.DEFINITION)).kind == "cloze"
    assert build_recall_item(_node(NodeType.THEOREM)).kind == "recall"
    assert build_recall_item(_node(NodeType.PROOF)).kind == "prove_step"
    assert build_recall_item(_node(NodeType.EXAMPLE)).kind == "apply"


def test_cloze_blanks_a_word_and_keeps_the_answer():
    item = build_recall_item(_node(NodeType.DEFINITION))
    assert "_____" in item.prompt
    assert item.answer in "alpha bravo charlie"


def test_items_only_for_verified_nodes():
    graph = build_fixture_graph()
    verify_graph(graph, SOURCES)              # marks all fixture nodes verified
    items = generate_recall_items(graph, SOURCES)
    assert len(items) == len(graph.nodes)
    assert all(i.grounded for i in items)     # fixture citations are all exact


def test_unverified_nodes_get_no_items():
    graph = build_fixture_graph()
    # Skip verification: nodes stay verified=False -> no questions generated.
    assert generate_recall_items(graph, SOURCES) == []
