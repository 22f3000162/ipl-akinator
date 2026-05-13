"""
engine/reasoning.py

Bayesian update logic — the core of the reasoning engine.

Given a user's answer to a question about attribute A,
this module updates every candidate's posterior score using the
probability that the player has attribute A.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.engine.candidate_pool import CandidatePool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Answer enum — canonical interpretation of user response
# ─────────────────────────────────────────────────────────────────────────────

class Answer(str, Enum):
    """
    Canonical answer enum produced by the Gemini Flash-Lite interpreter.

    YES       → User confirms the player has this attribute
    NO        → User denies the player has this attribute
    MAYBE     → User is uncertain (partial evidence)
    DONT_KNOW → User has no information (score unchanged)
    """
    YES       = "YES"
    NO        = "NO"
    MAYBE     = "MAYBE"
    DONT_KNOW = "DONT_KNOW"


# ─────────────────────────────────────────────────────────────────────────────
# Multiplier computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_multiplier(attribute_value: float, answer: Answer) -> float:
    """
    Compute the Bayesian likelihood multiplier for a single player.

    The multiplier is derived from how well the player's attribute value
    aligns with the user's answer.

    Parameters
    ----------
    attribute_value : float
        The player's value for the asked attribute (0.0 to 1.0).
    answer : Answer
        The user's interpreted answer.

    Returns
    -------
    float
        The likelihood multiplier to apply to this player's score.
        Always > 0 to prevent complete score annihilation.

    Multiplier formulas (locked in architecture spec):
    ─────────────────────────────────────────────────
    YES       → attribute_value
                (high attr value = more likely to be this player)
    NO        → 1 - attribute_value
                (low attr value = more likely to be this player)
    MAYBE     → 0.5 + 0.5 × attribute_value
                (soft update; pulls toward 0.5, still informative)
    DONT_KNOW → 1.0
                (no information — all players equally unaffected)
    """
    match answer:
        case Answer.YES:
            multiplier = attribute_value
        case Answer.NO:
            multiplier = 1.0 - attribute_value
        case Answer.MAYBE:
            multiplier = 0.5 + 0.5 * attribute_value
        case Answer.DONT_KNOW:
            multiplier = 1.0
        case _:
            raise ValueError(f"Unknown answer type: {answer!r}")

    # Floor at a small epsilon to prevent any player from being completely
    # eliminated by a single answer (guards against bad attribute data)
    return max(multiplier, 1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Main Bayesian update function
# ─────────────────────────────────────────────────────────────────────────────

def bayesian_update(
    pool: "CandidatePool",
    attribute: str,
    answer: Answer,
) -> dict[str, float]:
    """
    Apply a Bayesian update to all candidates in the pool.

    For each candidate:
      1. Retrieve their attribute value for the asked attribute
      2. Compute their likelihood multiplier based on the answer
      3. Multiply their current score by this value

    Then renormalize the entire pool.

    Parameters
    ----------
    pool : CandidatePool
        The live candidate pool to update in-place.
    attribute : str
        The attribute that was asked about (must be in ATTRIBUTE_NAMES).
    answer : Answer
        The user's interpreted answer.

    Returns
    -------
    dict[str, float]
        Map of {player_id: multiplier_applied} for logging/debugging.
    """
    scores = pool.get_all_scores()
    multipliers: dict[str, float] = {}

    for player_id in scores:
        player = pool.get_player(player_id)
        attr_val = player.get_attribute(attribute)
        multiplier = compute_multiplier(attr_val, answer)
        multipliers[player_id] = multiplier

    pool.multiply_scores(multipliers)  # also calls normalize() internally

    top_player, top_score = pool.top_candidate()
    logger.debug(
        "Bayesian update | attr=%s | answer=%s | top=%s (%.4f)",
        attribute, answer.value, top_player.name, top_score,
    )

    return multipliers
