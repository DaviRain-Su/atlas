"""Pipeline orchestration (ARCHITECTURE §3, §4).

Plain Python for now (no Prefect/Temporal yet — that is a later upgrade once we
need retries/observability/concurrency). Stages are explicit and each produces
an inspectable result, so the whole run is debuggable on a fixture.

    extract -> dedup -> verify (anti-hallucination) -> assemble (DAG check)

Extraction is behind the `Extractor` Protocol, so this runs offline with
`FakeExtractor` and unchanged with `ClaudeExtractor`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import Extractor, merge_duplicate_nodes
from .graph import CycleError, assemble
from .modality import ModalityDecision, decide_modality
from .schemas import KnowledgeGraph
from .verify import SourceText, VerificationReport, verify_graph


@dataclass
class PipelineResult:
    graph: KnowledgeGraph
    verification: VerificationReport
    learning_order: list[str] = field(default_factory=list)
    modalities: dict[str, ModalityDecision] = field(default_factory=dict)
    cycle: list[str] | None = None

    @property
    def ok(self) -> bool:
        """A run is OK when the verified subgraph assembles without a cycle."""
        return self.cycle is None


def run_pipeline(
    extractor: Extractor,
    document_id: str,
    title: str,
    sources: SourceText,
    *,
    drop_unverified: bool = True,
) -> PipelineResult:
    """Run the full decomposition pipeline on one document's sources."""
    # 1. Extract typed (unverified) graph.
    graph = extractor.extract(document_id, title, sources)

    # 2. Assembly pre-step: collapse duplicate references to the same object.
    graph = merge_duplicate_nodes(graph)

    # 3. Anti-hallucination gate: flip `verified` on grounded items.
    report = verify_graph(graph, sources)

    # 4. Optionally drop quarantined (unverified) items before assembly. This is
    #    the default per ARCHITECTURE §4.4: unverified items do not enter the graph.
    if drop_unverified:
        verified_ids = set(report.verified_nodes)
        graph = KnowledgeGraph(
            document_id=graph.document_id,
            title=graph.title,
            architecture=graph.architecture,
            nodes=[n for n in graph.nodes if n.verified],
            edges=[
                e
                for e in graph.edges
                if e.verified and e.src in verified_ids and e.dst in verified_ids
            ],
        )

    # 5. Modality decision per node (rules as code).
    modalities = {n.id: decide_modality(n.features) for n in graph.nodes}

    # 6. Assemble: integrity + acyclicity -> learning order. A cycle is a
    #    correctness alarm, not a crash; surface it in the result.
    result = PipelineResult(graph=graph, verification=report, modalities=modalities)
    try:
        result.learning_order = assemble(graph)
    except CycleError as exc:
        result.cycle = exc.cycle
    return result
