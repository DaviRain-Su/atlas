from datetime import datetime, timedelta, timezone

from atlas_engine.fixtures import build_fixture_graph
from atlas_engine.learner import (
    BKTParams,
    Card,
    LearnerModel,
    Rating,
    bkt_predict_correct,
    bkt_update,
    direct_prerequisites,
    interval_for_retention,
    retrievability,
    review_card,
    transitive_prerequisites,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --- BKT ---------------------------------------------------------------------

def test_bkt_correct_increases_mastery_wrong_decreases():
    p = 0.4
    assert bkt_update(p, correct=True) > p
    assert bkt_update(p, correct=False) < bkt_update(p, correct=True)


def test_bkt_converges_upward_with_repeated_success():
    p = 0.2
    for _ in range(8):
        p = bkt_update(p, correct=True)
    assert p > 0.95


def test_bkt_predict_in_unit_interval():
    assert 0.0 <= bkt_predict_correct(0.0) <= 1.0
    assert 0.0 <= bkt_predict_correct(1.0) <= 1.0
    assert bkt_predict_correct(0.9) > bkt_predict_correct(0.1)


# --- FSRS --------------------------------------------------------------------

def test_retrievability_decays_monotonically():
    s = 10.0
    assert retrievability(0, s) == 1.0
    assert retrievability(1, s) > retrievability(5, s) > retrievability(20, s)


def test_retrievability_about_0_9_at_stability():
    # FSRS is anchored so r ~= 0.9 when elapsed == stability.
    assert abs(retrievability(10.0, 10.0) - 0.9) < 0.01


def test_good_review_grows_interval_again_shrinks_it():
    first = review_card(Card(), Rating.GOOD, NOW)
    assert not first.is_new and first.reps == 1
    later = first.last_review + timedelta(days=interval_for_retention(first.stability))
    good = review_card(first, Rating.GOOD, later)
    again = review_card(first, Rating.AGAIN, later)
    assert good.stability > first.stability          # success strengthens memory
    assert again.stability <= first.stability         # lapse never strengthens
    assert again.lapses == 1
    assert good.due > again.due                        # easier recall -> later due


def test_easy_interval_at_least_good():
    g = review_card(Card(), Rating.GOOD, NOW)
    e = review_card(Card(), Rating.EASY, NOW)
    assert e.stability >= g.stability


# --- DAG navigation ----------------------------------------------------------

def test_prerequisite_navigation_matches_edge_convention():
    g = build_fixture_graph()
    # theorem depends_on function and epigraph -> those are its direct prereqs
    assert direct_prerequisites(g, "n_epi_theorem") == {"n_convex_fn", "n_epigraph"}
    # transitively, convex_set is underneath everything
    assert "n_convex_set" in transitive_prerequisites(g, "n_epi_theorem")


# --- Learner model ----------------------------------------------------------

def test_cold_start_lifts_prerequisite_priors():
    g = build_fixture_graph()
    lm = LearnerModel(g)
    base = lm.progress["n_convex_set"].p_known
    lm.apply_observed_mastery("n_epi_theorem")  # mastering the top implies the base
    assert lm.progress["n_convex_set"].p_known > base


def test_placement_nodes_rank_foundational_first():
    g = build_fixture_graph()
    lm = LearnerModel(g)
    # convex_set underlies the most nodes, so it should rank first to probe.
    assert lm.placement_nodes()[0] == "n_convex_set"


def test_learning_frontier_advances_as_prereqs_are_mastered():
    g = build_fixture_graph()
    lm = LearnerModel(g)
    # Nothing mastered: only the foundational node (no prereqs) is on the frontier.
    assert lm.learning_frontier() == ["n_convex_set"]
    # Master everything except the theorem; the theorem becomes reachable.
    for nid in ("n_convex_set", "n_convex_fn", "n_epigraph"):
        lm.progress[nid].p_known = 0.99
    assert "n_epi_theorem" in lm.learning_frontier()


def test_due_for_review_tracks_card_due_dates():
    g = build_fixture_graph()
    lm = LearnerModel(g)
    lm.review("n_convex_set", Rating.GOOD, NOW)
    assert "n_convex_set" not in lm.due_for_review(NOW)         # just scheduled out
    far = NOW + timedelta(days=365)
    assert "n_convex_set" in lm.due_for_review(far)             # eventually due
