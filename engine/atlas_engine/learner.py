"""Learner model + spaced-repetition scheduling (ARCHITECTURE §7; PRD §5.2.5/§5.2.6).

This is the module that makes the product "alive": it knows where on the graph a
given learner's understanding breaks, and therefore what to study next. Two
deterministic, fully-offline pieces:

  * Mastery tracking — Bayesian Knowledge Tracing (BKT) per node.
  * Scheduling — a compact implementation of the FSRS-5 forgetting curve and
    stability/difficulty updates, using the published default weights. Behavioral
    invariants are unit-tested; validate against py-fsrs before production.

Cold start (PRD §11.2): with no behavioural data we lean on the DAG prior —
prerequisites of an observed-mastered node are likely known too, and the
"learning frontier" is the set of not-yet-mastered nodes whose prerequisites are
all mastered. A small set of high-leverage placement nodes localizes a learner
fast without waiting for data to accumulate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from .schemas import KnowledgeGraph

# --- DAG navigation helpers --------------------------------------------------
# Edge convention (schemas.py): `src depends_on dst` => dst is a prerequisite of
# src. So a node's direct prerequisites are the dst's of its outgoing DAG edges.


def direct_prerequisites(graph: KnowledgeGraph, node_id: str) -> set[str]:
    return {e.dst for e in graph.dag_edges() if e.src == node_id}


def dependents(graph: KnowledgeGraph, node_id: str) -> set[str]:
    """Nodes that directly depend on `node_id`."""
    return {e.src for e in graph.dag_edges() if e.dst == node_id}


def transitive_prerequisites(graph: KnowledgeGraph, node_id: str) -> set[str]:
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        u = stack.pop()
        for p in direct_prerequisites(graph, u):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


# --- Bayesian Knowledge Tracing ----------------------------------------------


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.2     # P(L0): prior mastery before any evidence
    p_transit: float = 0.15  # P(T): chance of learning on an opportunity
    p_slip: float = 0.10    # P(S): known but answers wrong
    p_guess: float = 0.20   # P(G): unknown but answers right


def bkt_update(p_known: float, correct: bool, params: BKTParams = BKTParams()) -> float:
    """Posterior P(known) after one observation, then apply the learning step."""
    s, g = params.p_slip, params.p_guess
    if correct:
        num = p_known * (1 - s)
        den = num + (1 - p_known) * g
    else:
        num = p_known * s
        den = num + (1 - p_known) * (1 - g)
    posterior = num / den if den > 0 else p_known
    # Opportunity to transition from not-known to known.
    return posterior + (1 - posterior) * params.p_transit


def bkt_predict_correct(p_known: float, params: BKTParams = BKTParams()) -> float:
    """P(next answer correct) given current mastery."""
    return p_known * (1 - params.p_slip) + (1 - p_known) * params.p_guess


# --- FSRS-5 scheduling --------------------------------------------------------


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


_FACTOR = 19 / 81
_DECAY = -0.5

# Published FSRS-5 default weights.
_W = (
    0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046,
    1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315,
    2.9898, 0.51655, 0.6621,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def retrievability(elapsed_days: float, stability: float) -> float:
    """Probability of recall after `elapsed_days` given memory `stability`.

    FSRS power-law forgetting curve. Anchored so that at t == stability,
    retrievability ~= 0.9 (the design target).
    """
    if stability <= 0:
        return 0.0
    return (1 + _FACTOR * elapsed_days / stability) ** _DECAY


def interval_for_retention(stability: float, request_retention: float = 0.9) -> int:
    """Days until retrievability decays to `request_retention`. Min 1 day."""
    raw = (stability / _FACTOR) * (request_retention ** (1 / _DECAY) - 1)
    return max(1, round(raw))


def _init_stability(rating: Rating) -> float:
    return max(0.1, _W[rating - 1])


def _init_difficulty(rating: Rating) -> float:
    return _clamp(_W[4] - math.exp(_W[5] * (rating - 1)) + 1, 1.0, 10.0)


def _next_difficulty(difficulty: float, rating: Rating) -> float:
    delta = -_W[6] * (rating - 3)
    linear = difficulty + delta * (10 - difficulty) / 9  # damped, FSRS-5
    d0_easy = _clamp(_W[4] - math.exp(_W[5] * (Rating.EASY - 1)) + 1, 1.0, 10.0)
    reverted = _W[7] * d0_easy + (1 - _W[7]) * linear   # mean reversion
    return _clamp(reverted, 1.0, 10.0)


def _next_stability_recall(d: float, s: float, r: float, rating: Rating) -> float:
    hard_penalty = _W[15] if rating == Rating.HARD else 1.0
    easy_bonus = _W[16] if rating == Rating.EASY else 1.0
    growth = (
        math.exp(_W[8]) * (11 - d) * (s ** -_W[9])
        * (math.exp(_W[10] * (1 - r)) - 1) * hard_penalty * easy_bonus
    )
    return s * (1 + growth)


def _next_stability_forget(d: float, s: float, r: float) -> float:
    sf = _W[11] * (d ** -_W[12]) * ((s + 1) ** _W[13] - 1) * math.exp(_W[14] * (1 - r))
    return max(0.1, min(sf, s))  # post-lapse stability never exceeds prior


@dataclass
class Card:
    """FSRS scheduling state for one (learner, node) pair."""

    stability: float | None = None   # None => never reviewed
    difficulty: float | None = None
    due: datetime | None = None
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0

    @property
    def is_new(self) -> bool:
        return self.stability is None


def review_card(
    card: Card, rating: Rating, now: datetime, request_retention: float = 0.9
) -> Card:
    """Apply one review at `now`, returning the updated card. Pure (no mutation)."""
    if card.is_new:
        s = _init_stability(rating)
        d = _init_difficulty(rating)
    else:
        elapsed = max(0.0, (now - card.last_review).total_seconds() / 86400.0)
        r = retrievability(elapsed, card.stability)
        d = _next_difficulty(card.difficulty, rating)
        if rating == Rating.AGAIN:
            s = _next_stability_forget(d, card.stability, r)
        else:
            s = _next_stability_recall(d, card.stability, r, rating)

    interval = interval_for_retention(s, request_retention)
    return Card(
        stability=s,
        difficulty=d,
        due=now + timedelta(days=interval),
        last_review=now,
        reps=card.reps + 1,
        lapses=card.lapses + (1 if rating == Rating.AGAIN else 0),
    )


# --- Combined per-node progress + learner model ------------------------------


@dataclass
class NodeProgress:
    p_known: float
    card: Card = field(default_factory=Card)


class LearnerModel:
    """Per-node mastery (BKT) + scheduling (FSRS) for one learner over one graph."""

    def __init__(self, graph: KnowledgeGraph, params: BKTParams = BKTParams()):
        self.graph = graph
        self.params = params
        self.progress: dict[str, NodeProgress] = {
            n.id: NodeProgress(p_known=params.p_init) for n in graph.nodes
        }

    # -- cold start ----------------------------------------------------------
    def apply_observed_mastery(self, node_id: str, prior: float = 0.85) -> None:
        """Seed mastery for a node and lift the prior on its prerequisites.

        Used by the placement diagnostic: demonstrating an advanced node implies
        its prerequisites are likely known too (DAG prior, PRD §11.2).
        """
        if node_id in self.progress:
            self.progress[node_id].p_known = max(self.progress[node_id].p_known, prior)
        for pre in transitive_prerequisites(self.graph, node_id):
            cur = self.progress[pre].p_known
            self.progress[pre].p_known = max(cur, prior * 0.9)

    def placement_nodes(self, k: int | None = None) -> list[str]:
        """High-leverage nodes to probe first: the more nodes that ultimately
        depend on a node, the more a single answer tells us."""
        score = {n.id: 0 for n in self.graph.nodes}
        for n in self.graph.nodes:
            for pre in transitive_prerequisites(self.graph, n.id):
                score[pre] += 1
        ranked = sorted(self.graph.nodes, key=lambda n: (-score[n.id], n.id))
        ids = [n.id for n in ranked]
        return ids[:k] if k is not None else ids

    # -- review --------------------------------------------------------------
    def review(self, node_id: str, rating: Rating, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        prog = self.progress[node_id]
        prog.p_known = bkt_update(prog.p_known, rating != Rating.AGAIN, self.params)
        prog.card = review_card(prog.card, rating, now)

    # -- queries -------------------------------------------------------------
    def mastered_ids(self, threshold: float = 0.95) -> set[str]:
        return {nid for nid, p in self.progress.items() if p.p_known >= threshold}

    def learning_frontier(self, threshold: float = 0.95) -> list[str]:
        """Not-yet-mastered nodes whose prerequisites are all mastered.

        This is the answer to "what should this learner do next" — the readiness
        edge of the dependency graph (PRD §5.2.5)."""
        mastered = self.mastered_ids(threshold)
        frontier = [
            n.id
            for n in self.graph.nodes
            if n.id not in mastered
            and direct_prerequisites(self.graph, n.id) <= mastered
        ]
        return sorted(frontier)

    def due_for_review(self, now: datetime | None = None) -> list[str]:
        """Reviewed nodes whose retrievability has decayed to the review point."""
        now = now or datetime.now(timezone.utc)
        due = [
            nid
            for nid, p in self.progress.items()
            if p.card.due is not None and p.card.due <= now
        ]
        return sorted(due)
