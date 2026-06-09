"""
Async job pipeline.

- `JobStore` — MongoDB-backed system of record for jobs.
- `enqueue_poster_job` — create a job + push it onto the RQ (Redis) queue.
- `process_job` — the handler the worker runs (`jobs.handlers`).

Redis moves the work; MongoDB holds the durable job records.
"""

from __future__ import annotations

from esports_poster_ai.jobs.queue import QUEUE_NAME, enqueue_poster_job, get_queue, get_redis
from esports_poster_ai.jobs.store import JobStore

__all__ = ["JobStore", "enqueue_poster_job", "get_queue", "get_redis", "QUEUE_NAME"]
