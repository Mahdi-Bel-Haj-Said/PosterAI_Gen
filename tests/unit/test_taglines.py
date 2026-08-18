"""Curated tagline bank + the /v1/taglines endpoints."""

from __future__ import annotations

import random

from fastapi.testclient import TestClient

from esports_poster_ai.api.app import app
from esports_poster_ai.taglines import TAGLINES, list_taglines, random_tagline


def test_dataset_populated():
    assert len(TAGLINES["tournament_announcement"]) >= 5
    assert len(TAGLINES["tournament_banner"]) >= 5


def test_announcement_entries_have_a_subtagline():
    for e in TAGLINES["tournament_announcement"]:
        assert e["tagline"] and e["sub_tagline"]


def test_banner_entries_are_single_line():
    for e in TAGLINES["tournament_banner"]:
        assert e["tagline"] and e.get("sub_tagline") is None


def test_random_is_reproducible_and_in_pool():
    pick = random_tagline("tournament_announcement", rng=random.Random(1))
    assert pick in TAGLINES["tournament_announcement"]


def test_unknown_poster_type_falls_back_not_empty():
    assert list_taglines("gameday")  # falls back to a generic bank, never empty


def test_endpoint_random():
    c = TestClient(app)
    r = c.get("/v1/taglines/random", params={"poster_type": "tournament_announcement"})
    assert r.status_code == 200
    body = r.json()
    assert body["tagline"] and body["poster_type"] == "tournament_announcement"


def test_endpoint_list():
    c = TestClient(app)
    r = c.get("/v1/taglines", params={"poster_type": "tournament_banner"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 5
    assert all(t["sub_tagline"] is None for t in body["taglines"])
