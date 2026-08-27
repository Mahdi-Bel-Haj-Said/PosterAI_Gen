"""
One-time bootstrap: issue a platform's API key.

Run once, capture the plaintext key, put it in DEFENDR-BACKEND's
POSTER_AI_API_KEY, and never run it again unless you are rotating.

The key is shown ONCE — only its SHA-256 is stored. Losing it means issuing a
new one and revoking the old.

    python scripts/bootstrap_defendr_platform.py
    python scripts/bootstrap_defendr_platform.py --platform-id acme --name "Acme"
    python scripts/bootstrap_defendr_platform.py --list

Idempotent by default: if the platform already has a live key it refuses rather
than quietly minting a second one (two valid keys is a revocation hazard — you'd
rotate one and the other would keep working). Pass --force for a real rotation
where you want overlap, or --revoke-existing to replace outright.
"""

from __future__ import annotations

import argparse
import sys

from esports_poster_ai.auth.store import ApiKeyStore
from esports_poster_ai.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a platform API key.")
    parser.add_argument("--platform-id", default="defendr")
    parser.add_argument("--name", default="Defendr production integration")
    parser.add_argument(
        "--list", action="store_true", help="Show this platform's keys and exit."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Issue even if this platform already has a key (rotation with overlap).",
    )
    parser.add_argument(
        "--revoke-existing",
        action="store_true",
        help="Revoke all current keys for this platform before issuing the new one.",
    )
    args = parser.parse_args()

    store = ApiKeyStore(settings=get_settings())

    active = [k for k in store.list_for_platform(args.platform_id) if not k.revoked]

    if args.list:
        if not active:
            print(f"Platform '{args.platform_id}' has no active keys.")
            return 0
        print(f"Platform '{args.platform_id}' active keys:")
        for key in active:
            print(f"  - {key.key_id}  prefix={key.key_prefix}  created={key.created_at:%Y-%m-%d}")
        return 0

    if active and args.revoke_existing:
        for key in active:
            store.revoke(key.key_id)
            print(f"revoked {key.key_id} (prefix {key.key_prefix})")
        active = []

    if active and not args.force:
        print(f"Platform '{args.platform_id}' already has {len(active)} active key(s):")
        for key in active:
            print(f"  - {key.key_id}  prefix={key.key_prefix}  created={key.created_at:%Y-%m-%d}")
        print(
            "\nRefusing to issue a second key.\n"
            "  --revoke-existing   replace them (the old keys stop working)\n"
            "  --force             add another (both keep working — rotation with overlap)"
        )
        return 1

    api_key, plaintext = store.issue(platform_id=args.platform_id, name=args.name)

    # The row is committed at this point and the plaintext exists only in this
    # variable — print it before anything else can raise and strand the key.
    print(f"\nPOSTER_AI_API_KEY={plaintext}\n")

    print("=" * 72)
    print(f"  API key issued for platform: {args.platform_id}")
    print(f"  key_id : {api_key.key_id}")
    print(f"  prefix : {api_key.key_prefix}")
    print()
    print("  The line above is the PLAINTEXT key — shown once, never recoverable.")
    print("  Paste it into DEFENDR-BACKEND/.env.")
    print()
    print("  Server-side only. Never NEXT_PUBLIC_, never committed, never logged.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
