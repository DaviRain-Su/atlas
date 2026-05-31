"""Active-processing layer (ARCHITECTURE §7; PRD §5.2.6).

Retrieval practice, answer-first, and spaced repetition hang off graph nodes.
The *kind* of recall item is chosen by node type (definitions -> cloze;
theorems -> statement/condition recall; proofs -> prove-step; examples -> apply),
following the desirable-difficulties literature.

Item generation is deterministic here (template-based) so it is testable with no
key. The LLM-backed generator plugs in behind the same shape later and must pass
the SAME anti-hallucination gate (verify.py): a generated item is only usable if
it is grounded in the node's own citations. A practice question that hallucinates
is worse than none.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import KnowledgeGraph, Node, NodeType
from .verify import SourceText, is_grounded


@dataclass
class RecallItem:
    node_id: str
    kind: str          # cloze | recall | apply | prove_step
    prompt: str
    answer: str
    grounded: bool = False


# Which retrieval-practice kind fits each node type.
_KIND_BY_TYPE: dict[NodeType, str] = {
    NodeType.DEFINITION: "cloze",
    NodeType.NOTATION: "cloze",
    NodeType.AXIOM: "recall",
    NodeType.THEOREM: "recall",
    NodeType.LEMMA: "recall",
    NodeType.PROPOSITION: "recall",
    NodeType.COROLLARY: "recall",
    NodeType.PROOF: "prove_step",
    NodeType.EXAMPLE: "apply",
    NodeType.COUNTEREXAMPLE: "apply",
    NodeType.REMARK: "recall",
}


def _cloze(statement: str) -> tuple[str, str]:
    """Blank the longest word as a first-pass cloze deletion."""
    words = statement.split()
    if not words:
        return statement, ""
    target = max(words, key=len)
    blanked = statement.replace(target, "_____", 1)
    return blanked, target


def build_recall_item(node: Node) -> RecallItem:
    kind = _KIND_BY_TYPE.get(node.type, "recall")
    if kind == "cloze":
        prompt, answer = _cloze(node.statement)
        return RecallItem(node.id, kind, f"Fill in: {prompt}", answer)
    if kind == "prove_step":
        return RecallItem(
            node.id, kind,
            f"Reconstruct the next step of the proof for: {node.label}",
            node.statement,
        )
    if kind == "apply":
        return RecallItem(
            node.id, kind,
            f"Apply the idea in {node.label} to a new case. What does it show?",
            node.statement,
        )
    # recall
    return RecallItem(
        node.id, kind,
        f"State {node.label} and the conditions under which it holds.",
        node.statement,
    )


def generate_recall_items(
    graph: KnowledgeGraph, sources: SourceText | None = None
) -> list[RecallItem]:
    """One grounded recall item per verified node.

    If `sources` is given, each item is marked grounded only when the node's
    citations pass the verify gate — same discipline as extraction. Unverified
    nodes are skipped (no provenance => no question)."""
    items: list[RecallItem] = []
    for node in graph.nodes:
        if not node.verified:
            continue
        item = build_recall_item(node)
        if sources is not None:
            item.grounded = is_grounded(node.citations, sources)
        items.append(item)
    return items
