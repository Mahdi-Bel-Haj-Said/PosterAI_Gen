"""
`/v1/taglines` — the curated tagline bank.

Serves hand-written esports taglines so the frontend's "random tagline" button can
fill the field for users who'd rather not write their own. Static content (no org
scoping, no auth) — the same bank for everyone.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from esports_poster_ai.taglines import list_taglines, random_tagline

router = APIRouter(prefix="/v1/taglines", tags=["taglines"])


class Tagline(BaseModel):
    tagline: str
    sub_tagline: Optional[str] = None


class RandomTaglineResponse(Tagline):
    poster_type: str


class TaglineListResponse(BaseModel):
    poster_type: str
    taglines: List[Tagline]
    count: int


@router.get("/random", response_model=RandomTaglineResponse)
def get_random_tagline(
    poster_type: str = Query("tournament_announcement", description="Poster type to fit the tagline to."),
) -> RandomTaglineResponse:
    """One random {tagline, sub_tagline} for the poster type. Call again to re-roll."""
    pick: Dict[str, Optional[str]] = random_tagline(poster_type)
    return RandomTaglineResponse(
        poster_type=poster_type,
        tagline=pick["tagline"],
        sub_tagline=pick.get("sub_tagline"),
    )


@router.get("", response_model=TaglineListResponse)
def get_taglines(
    poster_type: str = Query("tournament_announcement", description="Poster type to fit the taglines to."),
) -> TaglineListResponse:
    """The whole tagline bank for a poster type (for a browse/picker UI)."""
    items = list_taglines(poster_type)
    return TaglineListResponse(
        poster_type=poster_type,
        taglines=[Tagline(tagline=i["tagline"], sub_tagline=i.get("sub_tagline")) for i in items],
        count=len(items),
    )


__all__ = ["router"]
