"""Extraction interface + a deterministic fake (ARCHITECTURE §4.3).

The real extractor is a multi-agent Claude pipeline (Opus for hard extraction,
Haiku for cheap classification), using structured output + citations + prompt
caching. That needs an API key and network, so it is intentionally NOT a hard
dependency of the engine.

Everything downstream (verify, assemble, modality, evals) depends only on the
`Extractor` Protocol below. `FakeExtractor` lets the whole pipeline run and be
tested offline on a fixture; `ClaudeExtractor` (claude_extractor.py) plugs into
the same interface when a key is present.
"""

from __future__ import annotations

from typing import Protocol

from .schemas import Edge, KnowledgeGraph, Node


class Extractor(Protocol):
    """Turns ingested source pages into a typed (unverified) knowledge graph."""

    def extract(
        self,
        document_id: str,
        title: str,
        sources: dict[tuple[str, int], str],
    ) -> KnowledgeGraph: ...


class FakeExtractor:
    """Returns a pre-baked graph, ignoring sources.

    Used to exercise the pipeline deterministically. The graph it returns is
    supplied at construction, so tests/fixtures stay in one place.
    """

    def __init__(self, graph: KnowledgeGraph):
        self._graph = graph

    def extract(
        self,
        document_id: str,
        title: str,
        sources: dict[tuple[str, int], str],
    ) -> KnowledgeGraph:
        return self._graph.model_copy(deep=True)


def merge_duplicate_nodes(graph: KnowledgeGraph) -> KnowledgeGraph:
    """Collapse nodes that share (type, normalized label) into one.

    Deductive books reference the same theorem from many places; assembly should
    not create duplicates. Citations are unioned; edges are repointed to the
    surviving id. Pure function — returns a new graph.
    """
    canonical: dict[tuple[str, str], str] = {}
    remap: dict[str, str] = {}
    kept: list[Node] = []

    for n in graph.nodes:
        key = (n.type.value, n.label.strip().lower())
        if key in canonical:
            survivor_id = canonical[key]
            remap[n.id] = survivor_id
            survivor = next(k for k in kept if k.id == survivor_id)
            survivor.citations.extend(n.citations)
        else:
            canonical[key] = n.id
            remap[n.id] = n.id
            kept.append(n)

    new_edges: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    for e in graph.edges:
        src, dst = remap[e.src], remap[e.dst]
        if src == dst:  # self-loop created by the merge -> drop
            continue
        sig = (src, dst, e.type.value)
        if sig in seen:
            continue
        seen.add(sig)
        new_edges.append(e.model_copy(update={"src": src, "dst": dst}))

    return KnowledgeGraph(
        document_id=graph.document_id,
        title=graph.title,
        architecture=graph.architecture,
        nodes=kept,
        edges=new_edges,
    )
