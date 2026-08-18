"""
Curated tagline dataset.

Good taglines make or break a poster, and not every user can write one. This is a
small, hand-written bank of esports taglines (game-agnostic — they read well for
League or Valorant) keyed by poster type. The frontend offers a "random" button
that fills the tagline field from here, so a user can either type their own or
roll one they can then edit.

Announcement taglines come as a (tagline, sub_tagline) pair; banner taglines are a
single punchy line. Add more freely — it's just data.
"""

from __future__ import annotations

import random as _random
from typing import Dict, List, Optional

# poster_type -> list of {tagline, sub_tagline?}. Uppercase because they render as
# the poster's hero text; the image model keeps the casing it's given.
TAGLINES: Dict[str, List[Dict[str, Optional[str]]]] = {
    "tournament_announcement": [
        {"tagline": "THE STAGE IS SET", "sub_tagline": "One will rise above all."},
        {"tagline": "LEGENDS ARE FORGED HERE", "sub_tagline": "Only one can be crowned."},
        {"tagline": "THE ROAD TO GLORY", "sub_tagline": "Every match. Everything on the line."},
        {"tagline": "CLASH OF CHAMPIONS", "sub_tagline": "The battle for supremacy begins."},
        {"tagline": "DESTINY AWAITS", "sub_tagline": "Who will make history?"},
        {"tagline": "WHERE LEGENDS COLLIDE", "sub_tagline": "The best of the best, one arena."},
        {"tagline": "GLORY OR NOTHING", "sub_tagline": "No second chances."},
        {"tagline": "THE HUNT BEGINS", "sub_tagline": "Glory favors the fearless."},
        {"tagline": "RISE TO THE OCCASION", "sub_tagline": "Champions aren't born. They're proven."},
        {"tagline": "THE THRONE IS CONTESTED", "sub_tagline": "Claim it, or fall."},
        {"tagline": "WRITTEN IN VICTORY", "sub_tagline": "History is made by the bold."},
        {"tagline": "ONE ARENA. ONE CROWN.", "sub_tagline": "Let the battle decide."},
        {"tagline": "THE FINAL ASCENT", "sub_tagline": "One summit. One champion."},
        {"tagline": "FORTUNE FAVORS THE FIERCE", "sub_tagline": "Step up or step aside."},
        {"tagline": "THE RECKONING", "sub_tagline": "Everything you've trained for, now."},
        # --- expanded bank (game-agnostic; works for LoL and Valorant) ---
        {"tagline": "SEIZE THE THRONE", "sub_tagline": "Only one may claim it."},
        {"tagline": "NO KINGS BY BIRTH", "sub_tagline": "Only those who earn it."},
        {"tagline": "THE CLIMB NEVER ENDS", "sub_tagline": "Every summit hides a higher one."},
        {"tagline": "BLEED FOR THE CROWN", "sub_tagline": "Greatness demands everything."},
        {"tagline": "PROVE IT HERE", "sub_tagline": "Talk means nothing now."},
        {"tagline": "BORN TO CONQUER", "sub_tagline": "Destiny bows to no one."},
        {"tagline": "THE LAST STAND", "sub_tagline": "Everything ends tonight."},
        {"tagline": "RIVALS AWAKEN", "sub_tagline": "Old scores demand an answer."},
        {"tagline": "CARVE YOUR NAME", "sub_tagline": "History remembers the bold."},
        {"tagline": "BURN THE BRACKET", "sub_tagline": "Leave nothing standing."},
        {"tagline": "ASCEND OR FALL", "sub_tagline": "There is no middle ground."},
        {"tagline": "THE CROWN AWAITS", "sub_tagline": "Reach out and take it."},
        {"tagline": "FEAR NO GIANT", "sub_tagline": "Legends fall to challengers."},
        {"tagline": "ETCHED IN GLORY", "sub_tagline": "Winners are never forgotten."},
        {"tagline": "THE GAUNTLET FALLS", "sub_tagline": "Answer or be forgotten."},
        {"tagline": "CHAMPIONS DON'T BLINK", "sub_tagline": "Hesitation is defeat."},
        {"tagline": "OWN THE MOMENT", "sub_tagline": "It will never come again."},
        {"tagline": "RISE UNBROKEN", "sub_tagline": "Pressure forges the great."},
        {"tagline": "WAR OF WILLS", "sub_tagline": "The fiercest heart survives."},
        {"tagline": "DESTINY IS EARNED", "sub_tagline": "No one hands you the crown."},
        {"tagline": "THE APEX BECKONS", "sub_tagline": "Only the relentless arrive."},
        {"tagline": "TAKE THE HEIGHTS", "sub_tagline": "The top belongs to the brave."},
        {"tagline": "LEGACY ON THE LINE", "sub_tagline": "Win now or fade forever."},
        {"tagline": "FORGED IN FIRE", "sub_tagline": "Pressure makes champions."},
        {"tagline": "ANSWER THE CALL", "sub_tagline": "Greatness is knocking."},
        {"tagline": "THE FINAL VERDICT", "sub_tagline": "Only one truth remains."},
        {"tagline": "CLAIM WHAT'S YOURS", "sub_tagline": "The crown was always waiting."},
        {"tagline": "SILENCE THE DOUBTERS", "sub_tagline": "Let the scoreboard speak."},
        {"tagline": "ENTER THE ARENA", "sub_tagline": "Leave everything on the field."},
        {"tagline": "MADE FOR THIS", "sub_tagline": "The moment finds the ready."},
        {"tagline": "OUTLAST THEM ALL", "sub_tagline": "The last one standing is king."},
        {"tagline": "NO RETREAT", "sub_tagline": "Only forward from here."},
        {"tagline": "THE GREAT DIVIDE", "sub_tagline": "Winners and everyone else."},
        {"tagline": "DEFY THE ODDS", "sub_tagline": "Upsets are written by the fearless."},
        {"tagline": "HUNGER WINS", "sub_tagline": "The starving fight hardest."},
        {"tagline": "STAKE YOUR CLAIM", "sub_tagline": "The summit has your name."},
        {"tagline": "THE WEIGHT OF GREATNESS", "sub_tagline": "Only the strong can carry it."},
        {"tagline": "BREAK THE DYNASTY", "sub_tagline": "Every reign has an end."},
        {"tagline": "ONE SHOT AT FOREVER", "sub_tagline": "Immortality is decided tonight."},
        {"tagline": "COURAGE UNDER FIRE", "sub_tagline": "Nerve separates the great."},
        {"tagline": "RULE OR SERVE", "sub_tagline": "The throne has no equals."},
        {"tagline": "THE STORM ARRIVES", "sub_tagline": "Weather it or be swept away."},
        {"tagline": "WRITE THE ENDING", "sub_tagline": "This story is yours to finish."},
        {"tagline": "GLORY HAS A PRICE", "sub_tagline": "Pay it in full."},
        {"tagline": "TITANS COLLIDE", "sub_tagline": "Only one leaves standing."},
        {"tagline": "SEIZE THE SUMMIT", "sub_tagline": "The peak rewards the fearless."},
        {"tagline": "THE CROWNING HOUR", "sub_tagline": "Destiny keeps no schedule but now."},
        {"tagline": "CONQUER OR CRUMBLE", "sub_tagline": "The arena forgives nothing."},
        {"tagline": "UNLEASH THE BEST", "sub_tagline": "Hold nothing back tonight."},
        {"tagline": "BECOME IMMORTAL", "sub_tagline": "Champions never truly leave."},
        {"tagline": "FEAR THE OLD BLOOD", "sub_tagline": "Legacy does not fall easily."},
        {"tagline": "IN THE NAME OF JUSTICE", "sub_tagline": "The verdict is decided in battle."},
        {"tagline": "NEVER SURRENDER", "sub_tagline": "The fight is never over."},
        {"tagline": "WITNESS PERFECTION", "sub_tagline": "Only flawless play survives."},
    ],
    "tournament_banner": [
        {"tagline": "THE ROAD TO GLORY", "sub_tagline": None},
        {"tagline": "WHERE LEGENDS COLLIDE", "sub_tagline": None},
        {"tagline": "THE STAGE IS SET", "sub_tagline": None},
        {"tagline": "CLASH OF CHAMPIONS", "sub_tagline": None},
        {"tagline": "DESTINY AWAITS", "sub_tagline": None},
        {"tagline": "ONLY ONE CAN RISE", "sub_tagline": None},
        {"tagline": "THE BATTLE BEGINS", "sub_tagline": None},
        {"tagline": "FORGED IN COMPETITION", "sub_tagline": None},
        {"tagline": "GLORY OR NOTHING", "sub_tagline": None},
        {"tagline": "THE HUNT IS ON", "sub_tagline": None},
        {"tagline": "CROWN THE BEST", "sub_tagline": None},
        {"tagline": "EARN YOUR LEGEND", "sub_tagline": None},
    ],
}

# Poster types that carry a tagline field today. Others fall back to the
# announcement bank (generic enough to reuse) so the endpoint never 404s.
_DEFAULT_KEY = "tournament_announcement"


def list_taglines(poster_type: Optional[str]) -> List[Dict[str, Optional[str]]]:
    """All taglines for a poster type (falls back to a generic bank)."""
    return TAGLINES.get((poster_type or "").strip().lower()) or TAGLINES[_DEFAULT_KEY]


def random_tagline(
    poster_type: Optional[str], *, rng: Optional[_random.Random] = None
) -> Dict[str, Optional[str]]:
    """Pick one random {tagline, sub_tagline} for the poster type."""
    pool = list_taglines(poster_type)
    return (rng or _random).choice(pool)


__all__ = ["TAGLINES", "list_taglines", "random_tagline"]
