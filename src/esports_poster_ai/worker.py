"""
RQ worker entry point.

Run with:

    python -m esports_poster_ai.worker            # run forever
    python -m esports_poster_ai.worker --burst     # drain the queue, then exit

It consumes the `poster-ai` queue and runs `jobs.handlers.process_job` for
each job. `--burst` is handy for tests and cron-style processing.

`SimpleWorker` is used (not the default forking `Worker`): it runs jobs in the
worker process itself, which works on Windows — the default worker relies on
`os.fork()`, unavailable there. For this workload (low volume, 20-60s jobs)
SimpleWorker is also perfectly adequate on Linux.
"""

from __future__ import annotations

import argparse
import logging

from esports_poster_ai.config import get_settings
from esports_poster_ai.jobs.queue import QUEUE_NAME, get_redis

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    from rq import Queue, SimpleWorker

    parser = argparse.ArgumentParser(description="EsportsPostAI async job worker")
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Process all currently queued jobs, then exit (instead of running forever).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    connection = get_redis(settings)
    queue = Queue(QUEUE_NAME, connection=connection)

    logger.info("worker.start", extra={"queue": QUEUE_NAME, "burst": args.burst})
    SimpleWorker([queue], connection=connection).work(burst=args.burst)


if __name__ == "__main__":
    main()
