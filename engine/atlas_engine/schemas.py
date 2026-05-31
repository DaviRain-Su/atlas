"""Typed property-graph schemas for the deductive knowledge architecture.

These mirror docs/ARCHITECTURE.md §5. The node/edge type tables and the
DAG-membership rule for edges live here as the single source of truth; the
Postgres DDL in db/ is generated to match.

Design rule (PRD §5.2.2): edges are *typed*, and not all of them belong in the
learning-order DAG. Symmetric / overlay edges (equivalent_to, intuition_for,
generalizes, counterexample_to) describe the book but must not constrain
topological ordering, or they would create spurious cycles.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class NodeType(str, Enum):
    """The smallest decomposition units for deductive books (ARCHITECTURE §5.1)."""

    DEFINITION = "definition"
    AXIOM = "axiom"
    NOTATION = "notation"
    LEMMA = "lemma"
    THEOREM = "theorem"
    PROPOSITION = "proposition"
    COROLLARY = "corollary"
    PROOF = "proof"
    EXAMPLE = "example"
    COUNTEREXAMPLE = "counterexample"
    REMARK = "remark"


class EdgeType(str, Enum):
    """Typed relations (ARCHITECTURE §5.2)."""

    DEPENDS_ON = "depends_on"            # A depends on B (B is prerequisite)
    USES = "uses"                        # A's proof uses B
    COROLLARY_OF = "corollary_of"        # A is a corollary of B
    SPECIAL_CASE_OF = "special_case_of"  # A is a special case of B
    PROVES = "proves"                    # proof P proves theorem T
    EXAMPLE_OF = "example_of"            # E is an example of C
    COUNTEREXAMPLE_TO = "counterexample_to"  # X is a counterexample to S (overlay)
    GENERALIZES = "generalizes"          # A generalizes B (overlay)
    EQUIVALENT_TO = "equivalent_to"      # A <-> B, symmetric (overlay)
    INTUITION_FOR = "intuition_for"      # R is an intuition for T (overlay)


# Edges that participate in the learning-order DAG (must stay acyclic).
# Everything else is a semantic overlay: it enriches navigation/teaching but
# does not constrain ordering. See ARCHITECTURE §5.2.
DAG_EDGE_TYPES: frozenset[EdgeType] = frozenset(
    {
        EdgeType.DEPENDS_ON,
        EdgeType.USES,
        EdgeType.COROLLARY_OF,
        EdgeType.SPECIAL_CASE_OF,
        EdgeType.PROVES,
        EdgeType.EXAMPLE_OF,
    }
)


class Entailment(str, Enum):
    """Result of the anti-hallucination grounding check (ARCHITECTURE §4.4)."""

    YES = "yes"
    PARTIAL = "partial"
    NO = "no"


class Citation(BaseModel):
    """Provenance: ties a node/edge back to an exact span of source text.

    The invariant that makes the graph trustworthy (PRD §5.2.3): `quote` must be
    the verbatim substring at (page_no, char_start..char_end). Verified by code,
    not by the model.
    """

    document_id: str
    page_no: int
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    quote: str
    entailment: Entailment = Entailment.PARTIAL
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    @model_validator(mode="after")
    def _spans_ordered(self) -> "Citation":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        return self


class NodeFeatures(BaseModel):
    """Content features that drive modality selection (ARCHITECTURE §6).

    Produced during extraction (cheap signals about the node's content), consumed
    by the rules-as-code modality layer. Kept separate so the decision function is
    a pure mapping that can be unit-tested in isolation.
    """

    is_process: bool = False              # unfolds over time (algorithm iteration)
    is_spatial: bool = False              # geometry / region / hyperplane
    is_multistep_derivation: bool = False  # multi-step proof
    is_abstract_symbolic: bool = False     # abstract / symbolic / definitional


class Node(BaseModel):
    id: str
    document_id: str
    type: NodeType
    label: str                 # "Theorem 3.2 (Strong duality)"
    statement: str             # normalized statement (may contain LaTeX)
    features: NodeFeatures = Field(default_factory=NodeFeatures)
    citations: list[Citation] = Field(default_factory=list)
    verified: bool = False


class Edge(BaseModel):
    id: str
    src: str                   # Node.id
    dst: str                   # Node.id
    type: EdgeType
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    citations: list[Citation] = Field(default_factory=list)
    verified: bool = False

    @property
    def in_dag(self) -> bool:
        """Whether this edge participates in the learning-order DAG."""
        return self.type in DAG_EDGE_TYPES

    @model_validator(mode="after")
    def _no_self_loop(self) -> "Edge":
        if self.src == self.dst:
            raise ValueError(f"self-loop edge on node {self.src!r}")
        return self


class KnowledgeGraph(BaseModel):
    """Assembled typed graph for one document."""

    document_id: str
    title: str
    architecture: str = "deductive"
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def dag_edges(self) -> list[Edge]:
        return [e for e in self.edges if e.in_dag]
