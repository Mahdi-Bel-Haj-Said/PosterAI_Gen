"""
Domain errors whose messages are safe to show end users.

The job handler stores the raw message of a `UserFacingError` (no exception-type
prefix) so the UI can display it directly, while unexpected errors keep the
techy `Type: detail` form for debugging.
"""

from __future__ import annotations


class UserFacingError(RuntimeError):
    """An error whose message is meaningful + safe to display to end users."""


class BackgroundRejectedError(UserFacingError):
    """The image model refused to analyze the chosen background.

    Almost always copyrighted / recognizable content (official game art,
    characters, or baked-in logos). The user should pick a different background.
    """


__all__ = ["UserFacingError", "BackgroundRejectedError"]
