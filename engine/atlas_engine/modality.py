"""Modality decision layer — rules as code (ARCHITECTURE §6, PRD §5.2.4).

This is the part that separates Atlas from commodity "chunk + quiz" tools, so it
is *not* vibes: it is an auditable, unit-testable pure function from node
features to a modality. Theory: Cognitive Load Theory + Mayer's multimedia
principles + the transient information effect.

Core counter-intuitive point (PRD §1.2): animation is NOT the default best
choice. For abstract/symbolic content it *increases* load. Animation earns its
keep only when content genuinely unfolds over time.
"""

from __future__ import annotations

from enum import Enum

from .schemas import NodeFeatures


class Modality(str, Enum):
    ANIMATION = "animation"              # learner-controlled playback
    STATIC_DIAGRAM = "static_diagram"    # + optional parameter interaction
    STEPWISE_REVEAL = "stepwise_reveal"  # + answer-first
    SELF_PACED_TEXT = "self_paced_text"  # + retrieval practice


class ModalityDecision:
    def __init__(self, modality: Modality, rationale: str):
        self.modality = modality
        self.rationale = rationale

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ModalityDecision({self.modality.value!r}, {self.rationale!r})"


def decide_modality(f: NodeFeatures) -> ModalityDecision:
    """Map node content features to a learning modality.

    Priority order is deliberate (see table in ARCHITECTURE §6):

    1. process/temporal  -> animation     (only place animation truly helps)
    2. spatial           -> static diagram (avoid transient-information load)
    3. multistep proof   -> stepwise reveal (chunk to lower intrinsic load)
    4. otherwise         -> self-paced text + retrieval practice
    """
    if f.is_process:
        return ModalityDecision(
            Modality.ANIMATION,
            "content unfolds over time (process/iteration); learner-controlled "
            "playback is where animation genuinely reduces load",
        )
    if f.is_spatial:
        return ModalityDecision(
            Modality.STATIC_DIAGRAM,
            "spatial content; a static diagram avoids the transient-information "
            "burden a video would impose",
        )
    if f.is_multistep_derivation:
        return ModalityDecision(
            Modality.STEPWISE_REVEAL,
            "multi-step derivation; reveal step-by-step with answer-first to "
            "lower intrinsic cognitive load",
        )
    return ModalityDecision(
        Modality.SELF_PACED_TEXT,
        "abstract/symbolic/definitional; self-paced text + retrieval practice "
        "(animation would increase load here)",
    )
