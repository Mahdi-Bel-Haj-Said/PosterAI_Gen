"""`python -m esports_poster_ai.api` — run the HTTP API with uvicorn."""

from __future__ import annotations

from esports_poster_ai.config import get_settings


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("esports_poster_ai.api.app:app", host=s.api_host, port=s.api_port)


if __name__ == "__main__":
    main()
