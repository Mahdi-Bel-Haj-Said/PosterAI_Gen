"""Tests for JobStore.content_metrics + set_rating (the metrics-dashboard data)."""

from __future__ import annotations

import mongomock

from esports_poster_ai.jobs.store import JobStore


def _store() -> JobStore:
    return JobStore(collection=mongomock.MongoClient()["testdb"]["jobs"])


def _input(vibe=None, energy=None, source=None, image_path=None, poster_type="gameday",
           quality="medium", game="league_of_legends", color_mode=None):
    design = {}
    if vibe: design["vibe"] = vibe
    if energy: design["energy"] = energy
    if color_mode: design["color_mode"] = color_mode
    bg = {}
    if source: bg["source"] = source
    if image_path: bg["image_path"] = image_path
    return {
        "_meta": {"game": game, "poster_type": poster_type, "quality": quality, "mode": "fresh"},
        "design": design,
        "background": bg,
    }


def _add(store, **kw):
    return store.create(input_data=_input(**kw), org_id="1", tournament_id="t", mode="fresh")


def test_dimension_counts_and_percentages():
    store = _store()
    _add(store, vibe="cosmic", energy="intense", source="generated")
    _add(store, vibe="cosmic", energy="intense", source="generated")
    _add(store, vibe="cyberpunk", energy="chill", image_path="/x.png")  # upload
    m = store.content_metrics()

    assert m["total_jobs"] == 3
    by_vibe = {k: v["count"] for k, v in m["counted"]["vibe"].items()}
    assert by_vibe == {"cosmic": 2, "cyberpunk": 1}
    assert m["counted"]["combo"]["intense_cosmic"]["count"] == 2
    # Background source normalises to ai_generated / upload.
    src = {k: v["count"] for k, v in m["counted"]["background_source"].items()}
    assert src == {"ai_generated": 2, "upload": 1}


def test_ratings_aggregate_overall_and_per_dimension():
    store = _store()
    j1 = _add(store, vibe="cosmic", energy="intense", source="generated")
    j2 = _add(store, vibe="cosmic", energy="intense", source="generated")
    j3 = _add(store, vibe="minimal", energy="chill", source="generated")
    # Mark completed so ratings are realistic, then rate two of them.
    for j in (j1, j2, j3):
        store.mark_completed(j.job_id, poster_id="p", storage_key="k", local_path="l")
    assert store.set_rating(j1.job_id, 5) is True
    store.set_rating(j2.job_id, 3)
    # j3 left unrated.

    m = store.content_metrics()
    assert m["ratings"]["count"] == 2
    assert m["ratings"]["sum"] == 8
    assert m["ratings"]["histogram"]["5"] == 1 and m["ratings"]["histogram"]["3"] == 1
    # cosmic got both ratings → sum 8 over 2.
    cosmic = m["counted"]["vibe"]["cosmic"]
    assert cosmic["rating_count"] == 2 and cosmic["rating_sum"] == 8
    # minimal unrated.
    assert m["counted"]["vibe"]["minimal"]["rating_count"] == 0


def test_set_rating_missing_job_returns_false():
    store = _store()
    assert store.set_rating("nope", 4) is False


def test_refine_jobs_without_design_dont_break_dimensions():
    store = _store()
    # A refine-style job: has _meta but no design/background.
    store.create(
        input_data={"_meta": {"game": "league_of_legends", "poster_type": "gameday", "quality": "high"}},
        org_id="1", tournament_id="t", mode="refine",
    )
    m = store.content_metrics()
    assert m["total_jobs"] == 1
    assert m["counted"]["vibe"] == {}          # no vibe → not counted
    assert m["counted"]["quality"]["high"]["count"] == 1
    assert m["counted"]["background_source"]["none"]["count"] == 1
