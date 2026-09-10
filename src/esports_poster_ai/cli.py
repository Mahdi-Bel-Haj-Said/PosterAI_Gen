"""
CLI entry point.

Workflows behind a single command:

1. Generate a poster synchronously:

       python run.py --input inputs/lol/gameday.json
       python run.py --input inputs/lol/gameday.json \\
           --mode consistency --tournament-id ewc_2025

2. Enqueue a poster as an async job (processed by the worker):

       python run.py --input inputs/lol/gameday.json --enqueue
       python run.py --job-status <job_id>

3. Extract a Style DNA from an approved poster:

       python run.py --extract-dna \\
           --source-poster outputs/poster_20260518_120000.png \\
           --tournament-id ewc_2025

4. Promote the extracted draft to the approved Style DNA:

       python run.py --approve-dna --tournament-id ewc_2025
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from esports_poster_ai.config import get_settings


def _setup_logging() -> None:
    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Esports Poster Generator")

    parser.add_argument("--input", help="Path to input JSON file (poster generation)")
    parser.add_argument("--mode", default="fresh", choices=["fresh", "consistency"])
    parser.add_argument("--tournament-id", default=None, help="Tournament identifier (consistency / DNA flows)")
    parser.add_argument("--org-id", default="1", help="Organization identifier (storage tenant; static for now)")

    # Async job flags.
    parser.add_argument(
        "--enqueue",
        action="store_true",
        help="Enqueue the --input poster as an async job instead of running it now.",
    )
    parser.add_argument(
        "--job-status",
        default=None,
        metavar="JOB_ID",
        help="Print the status of an async job by id.",
    )

    # DNA management flags.
    parser.add_argument(
        "--extract-dna",
        action="store_true",
        help="Extract a Style DNA from --source-poster and save as draft.",
    )
    parser.add_argument(
        "--approve-dna",
        action="store_true",
        help="Promote the draft DNA for --tournament-id to approved.",
    )
    parser.add_argument(
        "--source-poster",
        default=None,
        help="Path to the approved poster to extract DNA from.",
    )

    return parser


def _load_input_json(path: str, parser: argparse.ArgumentParser) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        parser.error(f"Input JSON not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_tournament_id(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.mode == "consistency" and not args.tournament_id:
        parser.error("--tournament-id is required for consistency mode.")
    return args.tournament_id or "_standalone"


def _run_generation(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    input_data = _load_input_json(args.input, parser)
    tournament_id = _resolve_tournament_id(args, parser)

    if args.mode == "consistency":
        from esports_poster_ai.modes.consistency import run_consistency

        result = run_consistency(input_data, tournament_id, org_id=args.org_id)
    else:
        from esports_poster_ai.modes.fresh import run_fresh

        result = run_fresh(input_data, org_id=args.org_id, tournament_id=tournament_id)

    print("\nPoster generated:")
    if result.local_path:
        print(f"  local:      {result.local_path}")
    print(f"  storage:    {result.storage_key}")
    print(f"  signed URL: {result.signed_url}")
    return 0


def _run_enqueue(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    input_data = _load_input_json(args.input, parser)
    tournament_id = _resolve_tournament_id(args, parser)

    from esports_poster_ai.jobs import enqueue_poster_job

    job = enqueue_poster_job(
        input_data=input_data,
        org_id=args.org_id,
        tournament_id=tournament_id,
        mode=args.mode,
    )
    print(f"\nJob enqueued: {job.job_id}")
    print(f"  mode:       {job.mode}")
    print(f"  status:     {job.status}")
    print(f"\nStart a worker to process it:  python -m esports_poster_ai.worker")
    print(f"Check progress:                python run.py --job-status {job.job_id}")
    return 0


def _run_job_status(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from esports_poster_ai.jobs import JobStore

    job = JobStore().get(args.job_status)
    if job is None:
        parser.error(f"No job found with id: {args.job_status}")
        return 2  # unreachable

    print(f"\nJob {job.job_id}")
    print(f"  status:    {job.status}")
    print(f"  mode:      {job.mode}")
    print(f"  org:       {job.org_id}")
    print(f"  tournament:{job.tournament_id}")
    print(f"  created:   {job.created_at}")
    print(f"  updated:   {job.updated_at}")

    if job.status == "completed" and job.storage_key:
        from esports_poster_ai.storage import get_storage

        print(f"  poster_id: {job.poster_id}")
        if job.local_path:
            print(f"  local:     {job.local_path}")
        print(f"  storage:   {job.storage_key}")
        print(f"  signed URL: {get_storage().signed_url(job.storage_key)}")
    elif job.status == "failed":
        print(f"  error:     {job.error}")
    return 0


def _run_extract_dna(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.source_poster:
        parser.error("--source-poster is required for --extract-dna.")
    if not args.tournament_id:
        parser.error("--tournament-id is required for --extract-dna.")

    src = Path(args.source_poster)
    if not src.exists():
        parser.error(f"Source poster not found: {src}")

    from esports_poster_ai.style_dna.extractor import extract_style_dna
    from esports_poster_ai.style_dna.repository import save_draft

    dna = extract_style_dna(
        poster_bytes=src.read_bytes(),
        tournament_id=args.tournament_id,
        source_reference=str(src),
    )
    key = save_draft(dna, args.org_id)

    # Echo a short summary so the user can sanity-check before promoting.
    preview = {
        "palette": dna.palette,
        "color_temperature": dna.color_temperature,
        "energy": dna.energy,
        "lighting": dna.lighting,
        "atmosphere": dna.atmosphere,
        "particle_effects": dna.particle_effects,
        "sd_style_keywords": dna.sd_style_keywords,
    }
    print(f"\nStyle DNA draft saved: {key}")
    print(json.dumps(preview, indent=2, ensure_ascii=False))
    print(
        f"\nReview the file. When you're happy with it, run:\n"
        f"    python run.py --approve-dna --tournament-id {args.tournament_id}\n"
    )
    return 0


def _run_approve_dna(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.tournament_id:
        parser.error("--tournament-id is required for --approve-dna.")

    from esports_poster_ai.style_dna.repository import promote_draft_to_approved

    try:
        dna, key = promote_draft_to_approved(args.org_id, args.tournament_id)
    except FileNotFoundError as e:
        parser.error(str(e))
        return 2  # unreachable

    print(f"\nStyle DNA approved for tournament '{dna.tournament_id}': {key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging()

    # Pick exactly one workflow.
    workflows = sum(
        1
        for f in (bool(args.input), args.extract_dna, args.approve_dna, bool(args.job_status))
        if f
    )
    if workflows == 0:
        parser.error("Specify one of --input, --extract-dna, --approve-dna, or --job-status.")
    if workflows > 1:
        parser.error(
            "Pick one workflow: --input, --extract-dna, --approve-dna, or --job-status."
        )

    if args.job_status:
        return _run_job_status(args, parser)
    if args.extract_dna:
        return _run_extract_dna(args, parser)
    if args.approve_dna:
        return _run_approve_dna(args, parser)
    if args.enqueue:
        return _run_enqueue(args, parser)
    return _run_generation(args, parser)


if __name__ == "__main__":
    sys.exit(main())
