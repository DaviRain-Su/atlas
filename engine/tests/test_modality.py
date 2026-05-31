from atlas_engine.modality import Modality, decide_modality
from atlas_engine.schemas import NodeFeatures


def test_process_wins_animation():
    d = decide_modality(NodeFeatures(is_process=True))
    assert d.modality is Modality.ANIMATION


def test_spatial_gets_static_diagram():
    d = decide_modality(NodeFeatures(is_spatial=True))
    assert d.modality is Modality.STATIC_DIAGRAM


def test_multistep_gets_stepwise_reveal():
    d = decide_modality(NodeFeatures(is_multistep_derivation=True))
    assert d.modality is Modality.STEPWISE_REVEAL


def test_abstract_default_is_self_paced_text():
    # The counter-intuitive core: abstract content does NOT get animation.
    d = decide_modality(NodeFeatures(is_abstract_symbolic=True))
    assert d.modality is Modality.SELF_PACED_TEXT
    assert decide_modality(NodeFeatures()).modality is Modality.SELF_PACED_TEXT


def test_priority_process_over_spatial():
    # When several features fire, process (animation) takes precedence.
    d = decide_modality(NodeFeatures(is_process=True, is_spatial=True))
    assert d.modality is Modality.ANIMATION


def test_decision_carries_rationale():
    assert decide_modality(NodeFeatures(is_spatial=True)).rationale
