"""Anti-hallucination verification gate (ARCHITECTURE §4.4, PRD §5.2.3).

Two independent checks, both deterministic and free:

1. Quote exactness: the citation `quote` must be the verbatim substring at
   (page_no, char_start..char_end) in the source. Catches fabricated citations
   at zero cost.
2. Groundedness: a node/edge is "grounded" iff it has >=1 citation whose quote
   matches exactly AND whose entailment is at least PARTIAL.

The entailment judgement itself (yes/partial/no) is produced upstream by an
independent LLM pass; here we only enforce the gate so the rule is testable
without a model. `verified` defaults to False, so unverified items do not enter
the graph unless this gate flips them.
"""

from __future__ import annotations

from .schemas import Citation, Edge, Entailment, KnowledgeGraph, Node

# Pages of source text, keyed by (document_id, page_no).
SourceText = dict[tuple[str, int], str]


def quote_matches(citation: Citation, sources: SourceText) -> bool:
    """True iff `quote` is exactly the source substring at the cited span."""
    page = sources.get((citation.document_id, citation.page_no))
    if page is None:
        return False
    if citation.char_end > len(page):
        return False
    return page[citation.char_start : citation.char_end] == citation.quote


def is_grounded(citations: list[Citation], sources: SourceText) -> bool:
    """A node/edge is grounded if any citation matches exactly and entails it."""
    for c in citations:
        if c.entailment is Entailment.NO:
            continue
        if quote_matches(c, sources):
            return True
    return False


class VerificationReport:
    def __init__(self) -> None:
        self.verified_nodes: list[str] = []
        self.quarantined_nodes: list[str] = []
        self.verified_edges: list[str] = []
        self.quarantined_edges: list[str] = []
        self.bad_quotes: list[str] = []  # citations that failed exact match

    @property
    def grounded_rate(self) -> float:
        total = len(self.verified_nodes) + len(self.quarantined_nodes)
        return len(self.verified_nodes) / total if total else 0.0


def verify_graph(graph: KnowledgeGraph, sources: SourceText) -> VerificationReport:
    """Flip `verified` on grounded nodes/edges; quarantine the rest in place.

    Mutates the graph (sets `verified`) and returns a report with the metrics the
    evals harness consumes (notably grounded_rate, PRD §9).
    """
    report = VerificationReport()

    for node in graph.nodes:
        for c in node.citations:
            if not quote_matches(c, sources):
                report.bad_quotes.append(f"node:{node.id}")
        if is_grounded(node.citations, sources):
            node.verified = True
            report.verified_nodes.append(node.id)
        else:
            node.verified = False
            report.quarantined_nodes.append(node.id)

    for edge in graph.edges:
        for c in edge.citations:
            if not quote_matches(c, sources):
                report.bad_quotes.append(f"edge:{edge.id}")
        # An edge can be grounded by its own citations, or, lacking any, by both
        # endpoints being verified (a structural edge inferred from verified nodes).
        if edge.citations:
            grounded = is_grounded(edge.citations, sources)
        else:
            verified_ids = set(report.verified_nodes)
            grounded = edge.src in verified_ids and edge.dst in verified_ids
        edge.verified = grounded
        (report.verified_edges if grounded else report.quarantined_edges).append(edge.id)

    return report
