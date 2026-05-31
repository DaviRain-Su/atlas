"""A tiny deductive fixture used by the CLI demo and the tests.

It models a sliver of convex-optimization-style material so the pipeline can be
exercised end-to-end offline. Source "pages" are real strings, and every node's
citation quote is an exact substring of them, so the anti-hallucination gate
genuinely runs (rather than being mocked).
"""

from __future__ import annotations

from .schemas import (
    Citation,
    Edge,
    EdgeType,
    Entailment,
    KnowledgeGraph,
    Node,
    NodeFeatures,
    NodeType,
)

DOC_ID = "convex-demo"

# --- Source text (what ingest would produce: text keyed by (doc, page)) -------
PAGE_1 = (
    "A set C is convex if the line segment between any two points in C lies in C. "
    "Formally, for any x1, x2 in C and any theta with 0 <= theta <= 1, "
    "the point theta*x1 + (1-theta)*x2 belongs to C."
)
PAGE_2 = (
    "A function f is convex if its domain is a convex set and for all x, y in the "
    "domain and theta in [0,1], f(theta x + (1-theta) y) <= theta f(x) + (1-theta) f(y). "
    "The epigraph of a function is the set of points lying on or above its graph. "
    "Theorem: a function is convex if and only if its epigraph is a convex set."
)

SOURCES: dict[tuple[str, int], str] = {
    (DOC_ID, 1): PAGE_1,
    (DOC_ID, 2): PAGE_2,
}


def _span(page_no: int, text: str, needle: str, entailment: Entailment) -> Citation:
    start = text.index(needle)
    return Citation(
        document_id=DOC_ID,
        page_no=page_no,
        char_start=start,
        char_end=start + len(needle),
        quote=needle,
        entailment=entailment,
        confidence=0.9,
    )


def build_fixture_graph() -> KnowledgeGraph:
    """Hand-built graph whose citations all point at real source spans."""
    convex_set = Node(
        id="n_convex_set",
        document_id=DOC_ID,
        type=NodeType.DEFINITION,
        label="Definition (Convex set)",
        statement="A set C is convex if the segment between any two points lies in C.",
        features=NodeFeatures(is_spatial=True),
        citations=[_span(1, PAGE_1, "A set C is convex if the line segment", Entailment.YES)],
    )
    convex_fn = Node(
        id="n_convex_fn",
        document_id=DOC_ID,
        type=NodeType.DEFINITION,
        label="Definition (Convex function)",
        statement="f is convex if dom f is convex and Jensen's inequality holds.",
        features=NodeFeatures(is_abstract_symbolic=True),
        citations=[_span(2, PAGE_2, "A function f is convex if its domain", Entailment.YES)],
    )
    epigraph = Node(
        id="n_epigraph",
        document_id=DOC_ID,
        type=NodeType.DEFINITION,
        label="Definition (Epigraph)",
        statement="The epigraph is the set of points on or above the graph of f.",
        features=NodeFeatures(is_spatial=True),
        citations=[_span(2, PAGE_2, "The epigraph of a function is the set", Entailment.YES)],
    )
    epi_thm = Node(
        id="n_epi_theorem",
        document_id=DOC_ID,
        type=NodeType.THEOREM,
        label="Theorem (Convexity via epigraph)",
        statement="f is convex iff its epigraph is a convex set.",
        features=NodeFeatures(is_abstract_symbolic=True),
        citations=[_span(2, PAGE_2, "a function is convex if and only if its epigraph", Entailment.YES)],
    )

    nodes = [convex_set, convex_fn, epigraph, epi_thm]
    edges = [
        # The epigraph theorem ties the function definition to the set definition.
        Edge(id="e1", src="n_epi_theorem", dst="n_convex_fn", type=EdgeType.DEPENDS_ON, confidence=0.9),
        Edge(id="e2", src="n_epi_theorem", dst="n_epigraph", type=EdgeType.DEPENDS_ON, confidence=0.9),
        Edge(id="e3", src="n_epigraph", dst="n_convex_set", type=EdgeType.DEPENDS_ON, confidence=0.8),
        Edge(id="e4", src="n_convex_fn", dst="n_convex_set", type=EdgeType.DEPENDS_ON, confidence=0.7),
        # Overlay edge (does NOT enter the DAG): the theorem gives intuition for
        # the function definition. Even though it points "back", it must not
        # create a cycle, because intuition_for is not a DAG edge.
        Edge(id="e5", src="n_epi_theorem", dst="n_convex_fn", type=EdgeType.INTUITION_FOR, confidence=0.6),
    ]
    return KnowledgeGraph(document_id=DOC_ID, title="Convex (demo)", nodes=nodes, edges=edges)


def build_gold_graph() -> KnowledgeGraph:
    """Gold set for evals — here identical to the fixture (perfect-extractor case)."""
    return build_fixture_graph()
