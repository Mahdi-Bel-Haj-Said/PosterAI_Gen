"""
RQ worker entry point.

Run with:

    python -m esports_poster_ai.worker            # run forever
    python -m esports_poster_ai.worker --burst     # drain the queue, then exit

It consumes the `poster-ai` queue (running `jobs.handlers.process_job`) and the
`epai-webhooks` queue (running `webhooks.delivery.deliver_webhook`). The webhook
queue stays empty unless WEBHOOKS_ENABLED is on and a platform has a config, so
this is a no-op for the default setup. `--burst` is handy for tests.

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

    from esports_poster_ai.webhooks.delivery import WEBHOOK_QUEUE

    connection = get_redis(settings)
    # Posters first (higher priority), then webhook deliveries. The webhook queue
    # is empty unless webhooks are enabled + configured, so this adds no overhead.
    queues = [Queue(QUEUE_NAME, connection=connection), Queue(WEBHOOK_QUEUE, connection=connection)]

    logger.info(
        "worker.start",
        extra={"queues": [QUEUE_NAME, WEBHOOK_QUEUE], "burst": args.burst},
    )

    # Crash recovery: if a durable bank refill was interrupted (leftover pending
    # work) and no drainer is alive, resume it in a detached process. Off the burst
    # path (tests) and fully guarded — worker startup must never fail on this.
    if not args.burst:
        try:
            from esports_poster_ai.bank.drain import ensure_drain_running

            if ensure_drain_running(settings=settings, only_if_pending=True):
                logger.info("worker.resumed_bank_refill")
        except Exception as e:  # noqa: BLE001
            logger.warning("worker.refill_recovery_failed", extra={"error": str(e)})

    SimpleWorker(queues, connection=connection).work(burst=args.burst)


if __name__ == "__main__":
    main()
