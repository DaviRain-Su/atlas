"""Evals harness — the moat's hard guarantee (ARCHITECTURE §9, PRD §9).

Without measurement you cannot tell whether the graph truly understands the book
or is a confident hallucination. This computes the metrics that matter and
ignores vanity metrics (pages/books generated).

Metrics:
  * node/edge precision & recall against a hand-labelled gold set
  * grounded_rate (source traceability) — the anti-hallucination hard metric
  * DAG health: cycle count (must be 0), orphan-node rate
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import find_cycle
from .pipeline import PipelineResult
from .schemas import Edge, KnowledgeGraph, Node


@dataclass
class PRF:
    precision: float
    recall: float

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _node_key(n: Node) -> tuple[str, str]:
    return (n.type.value, n.label.strip().lower())


def _edge_key(e: Edge) -> tuple[str, str, str]:
    # Compared on (src,dst,type); ids are run-specific so excluded.
    return (e.src, e.dst, e.type.value)


def _prf(predicted: set, gold: set) -> PRF:
    if not predicted and not gold:
        return PRF(1.0, 1.0)
    tp = len(predicted & gold)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold) if gold else 0.0
    return PRF(precision, recall)


def node_prf(predicted: KnowledgeGraph, gold: KnowledgeGraph) -> PRF:
    return _prf({_node_key(n) for n in predicted.nodes}, {_node_key(n) for n in gold.nodes})


def edge_prf(predicted: KnowledgeGraph, gold: KnowledgeGraph) -> PRF:
    return _prf({_edge_key(e) for e in predicted.edges}, {_edge_key(e) for e in gold.edges})


def orphan_rate(graph: KnowledgeGraph) -> float:
    """Fraction of nodes touched by no edge at all (likely extraction misses)."""
    if not graph.nodes:
        return 0.0
    touched: set[str] = set()
    for e in graph.edges:
        touched.add(e.src)
        touched.add(e.dst)
    orphans = graph.node_ids() - touched
    return len(orphans) / len(graph.nodes)


@dataclass
class EvalReport:
    nodes: PRF
    edges: PRF
    grounded_rate: float
    cycle_count: int  # 0 or 1 (we surface the first cycle found)
    orphan_rate: float

    def summary(self) -> str:
        return (
            f"nodes  P={self.nodes.precision:.2f} R={self.nodes.recall:.2f} "
            f"F1={self.nodes.f1:.2f}\n"
            f"edges  P={self.edges.precision:.2f} R={self.edges.recall:.2f} "
            f"F1={self.edges.f1:.2f}\n"
            f"grounded_rate = {self.grounded_rate:.2f}\n"
            f"cycles        = {self.cycle_count} (must be 0)\n"
            f"orphan_rate   = {self.orphan_rate:.2f}"
        )


def evaluate(result: PipelineResult, gold: KnowledgeGraph) -> EvalReport:
    return EvalReport(
        nodes=node_prf(result.graph, gold),
        edges=edge_prf(result.graph, gold),
        grounded_rate=result.verification.grounded_rate,
        cycle_count=0 if find_cycle(result.graph) is None else 1,
        orphan_rate=orphan_rate(result.graph),
    )
