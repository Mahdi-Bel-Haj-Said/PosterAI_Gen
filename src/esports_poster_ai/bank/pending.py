"""
Durable pending-background store + drain coordinator (MongoDB-backed).

The auto-refill must ALWAYS eventually fill the bank — even if the serverless GPU
is unavailable for a long time. In-memory prompts would be lost on a crash, and a
skip-on-timeout would leave the bank under-filled. So a refill's work is persisted
here as **pending records**, one per background still owed, and a drain loop keeps
retrying each until it is generated AND uploaded (then the record is deleted).

Two collections:
- `bg_bank_pending`  — one doc per owed background (the durable work queue).
- `bg_bank_drain`    — a single heartbeat/claim doc giving single-flight + crash
                       recovery for the drain process.

`pymongo` is imported lazily; tests inject a `mongomock` collection directly.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

PENDING_COLLECTION = "bg_bank_pending"
DRAIN_COLLECTION = "bg_bank_drain"
_DRAIN_ID = "drain"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PendingBackgroundStore:
    """The durable work queue of backgrounds still owed to the bank."""

    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db][PENDING_COLLECTION]

    # ---------------------------------------------------------------- write
    def add_tasks(self, tasks: List[Dict[str, Any]], *, batch_id: str) -> int:
        """Insert one pending record per owed background. Returns how many added."""
        if not tasks:
            return 0
        now = _now()
        docs = [
            {
                "batch_id": batch_id,
                "combo_slug": t["combo_slug"],
                "prompt_text": t["prompt_text"],
                "negative_prompt": t.get("negative_prompt", ""),
                "width": t["width"],
                "height": t["height"],
                "seed": t["seed"],
                "status": "pending",
                "attempts": 0,
                "last_error": None,
                "not_before": now,
                "claimed_at": None,
                "created_at": now,
                "updated_at": now,
            }
            for t in tasks
        ]
        self._col.insert_many(docs)
        logger.info("bank.pending.added", extra={"count": len(docs), "batch_id": batch_id})
        return len(docs)

    def claim_one(self, *, stale_after_s: int = 1800) -> Optional[Dict[str, Any]]:
        """
        Atomically claim the next runnable record → mark it in_progress.

        Runnable = pending (past its not_before backoff), OR in_progress but stale
        (claimed longer than `stale_after_s` ago — its worker likely died). Returns
        the claimed doc, or None if nothing is runnable right now.
        """
        now = _now()
        stale_cutoff = now - timedelta(seconds=stale_after_s)
        query = {
            "$or": [
                {"status": "pending", "not_before": {"$lte": now}},
                {"status": "in_progress", "claimed_at": {"$lt": stale_cutoff}},
            ]
        }
        return self._col.find_one_and_update(
            query,
            {"$set": {"status": "in_progress", "claimed_at": now, "updated_at": now}},
            sort=[("created_at", 1)],
            return_document=True,  # ReturnDocument.AFTER == True in pymongo
        )

    def mark_done(self, task_id: Any) -> None:
        """A background was generated AND uploaded — remove it from the queue."""
        self._col.delete_one({"_id": task_id})

    def mark_failed(self, task_id: Any, *, error: str, backoff_s: int = 15) -> None:
        """Return a record to pending for retry, with a short backoff. Never gives up."""
        now = _now()
        self._col.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "pending",
                    "claimed_at": None,
                    "last_error": error[:400],
                    "not_before": now + timedelta(seconds=backoff_s),
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
        )

    # ---------------------------------------------------------------- read
    def count_remaining(self) -> int:
        """Total records still owed (pending + in_progress)."""
        return self._col.count_documents({})

    def remaining_by_combo(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for doc in self._col.find({}, {"combo_slug": 1, "_id": 0}):
            slug = doc.get("combo_slug", "?")
            counts[slug] = counts.get(slug, 0) + 1
        return counts


class DrainCoordinator:
    """
    Single-flight + crash-recovery for the drain process, via one Mongo doc.

    `claim()` atomically wins ownership only if no live drainer is beating the
    heartbeat; the owner calls `beat()` periodically. `is_live()` lets the trigger
    decide whether a drainer is already running (skip) or dead (respawn).
    """

    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db][DRAIN_COLLECTION]
        self._owner = f"{os.getpid()}"

    def is_live(self, *, within_s: int = 90) -> bool:
        """True if a drainer beat the heartbeat within `within_s` seconds."""
        doc = self._col.find_one({"_id": _DRAIN_ID})
        if not doc or not doc.get("ts"):
            return False
        return doc["ts"] >= _now() - timedelta(seconds=within_s)

    def claim(self, *, stale_after_s: int = 90) -> bool:
        """
        Atomically become the drainer iff none is live. Returns True if we own it.

        Wins when the heartbeat doc is missing or stale (older than stale_after_s).
        """
        now = _now()
        stale_cutoff = now - timedelta(seconds=stale_after_s)
        res = self._col.update_one(
            {"_id": _DRAIN_ID, "$or": [{"ts": {"$lt": stale_cutoff}}, {"ts": None}]},
            {"$set": {"ts": now, "owner": self._owner}},
        )
        if res.modified_count == 1:
            return True
        # No existing doc at all → insert (first ever run). Ignore duplicate races.
        try:
            self._col.insert_one({"_id": _DRAIN_ID, "ts": now, "owner": self._owner})
            return True
        except Exception:  # noqa: BLE001 — someone inserted first; they own it
            return False

    def beat(self) -> None:
        self._col.update_one(
            {"_id": _DRAIN_ID}, {"$set": {"ts": _now(), "owner": self._owner}}, upsert=True
        )

    def release(self) -> None:
        """Mark the drainer as gone so the next trigger respawns immediately."""
        self._col.update_one({"_id": _DRAIN_ID}, {"$set": {"ts": None, "owner": None}})


__all__ = ["PendingBackgroundStore", "DrainCoordinator", "PENDING_COLLECTION", "DRAIN_COLLECTION"]
