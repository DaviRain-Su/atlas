import pytest
from pydantic import ValidationError

from atlas_engine.schemas import (
    DAG_EDGE_TYPES,
    Citation,
    Edge,
    EdgeType,
    Entailment,
)


def test_dag_membership_matches_spec():
    # DAG edges (ordering) vs overlay edges (semantic only). ARCHITECTURE §5.2.
    assert Edge(id="e", src="a", dst="b", type=EdgeType.DEPENDS_ON).in_dag
    assert Edge(id="e", src="a", dst="b", type=EdgeType.PROVES).in_dag
    assert not Edge(id="e", src="a", dst="b", type=EdgeType.EQUIVALENT_TO).in_dag
    assert not Edge(id="e", src="a", dst="b", type=EdgeType.INTUITION_FOR).in_dag
    assert not Edge(id="e", src="a", dst="b", type=EdgeType.GENERALIZES).in_dag


def test_overlay_and_dag_types_partition_all_edge_types():
    overlay = {
        EdgeType.COUNTEREXAMPLE_TO,
        EdgeType.GENERALIZES,
        EdgeType.EQUIVALENT_TO,
        EdgeType.INTUITION_FOR,
    }
    assert DAG_EDGE_TYPES | overlay == set(EdgeType)
    assert DAG_EDGE_TYPES & overlay == set()


def test_self_loop_rejected():
    with pytest.raises(ValidationError):
        Edge(id="e", src="x", dst="x", type=EdgeType.DEPENDS_ON)


def test_citation_span_order_validated():
    with pytest.raises(ValidationError):
        Citation(
            document_id="d", page_no=1, char_start=10, char_end=5,
            quote="x", entailment=Entailment.YES,
        )
