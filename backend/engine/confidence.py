"""
engine/confidence.py

Confidence checker — decides when the engine is ready to make its final guess.

Two triggers (either fires a guess):
  1. Top candidate's posterior probability >= CONFIDENCE_THRESHOLD (0.80)
  2. questions_asked >= MAX_QUESTIONS (12)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.engine.candidate_pool import CandidatePool

logger = logging.getLogger(__name__)

# Locked in architecture spec — updated to ≤12 questions
CONFIDENCE_THRESHOLD: float = 0.80
MAX_QUESTIONS: int = 12


class GuessReason(str, Enum):
    """Why the system decided to make its guess."""
    CONFIDENCE    = "confidence"      # hit the 0.80 threshold
    MAX_QUESTIONS = "max_questions"   # ran out of questions
    NOT_YET       = "not_yet"         # keep playing


@dataclass
class ConfidenceResult:
    """
    Result of a confidence check.

    Attributes
    ----------
    should_guess : bool
        If True, the engine should stop asking and reveal its guess.
    reason : GuessReason
        Why the decision was made.
    top_score : float
        The current highest posterior probability.
    questions_asked : int
        How many questions have been asked so far.
    """
    should_guess: bool
    reason: GuessReason
    top_score: float
    questions_asked: int

    def __repr__(self) -> str:
        return (
            f"ConfidenceResult("
            f"should_guess={self.should_guess}, "
            f"reason={self.reason.value!r}, "
            f"top_score={self.top_score:.4f}, "
            f"q={self.questions_asked})"
        )


def check_confidence(
    pool: "CandidatePool",
    questions_asked: int,
    threshold: float = CONFIDENCE_THRESHOLD,
    max_questions: int = MAX_QUESTIONS,
) -> ConfidenceResult:
    """
    Evaluate whether the engine should make its final guess.

    Parameters
    ----------
    pool : CandidatePool
        Current candidate pool with up-to-date posterior scores.
    questions_asked : int
        Number of questions asked so far this session.
    threshold : float
        Minimum posterior probability to trigger a confidence guess.
        Default: 0.80 (from architecture spec).
    max_questions : int
        Maximum number of questions before forcing a guess.
        Default: 12 (updated from original 8).

    Returns
    -------
    ConfidenceResult
        Contains whether to guess, why, and current top score.
    """
    _, top_score = pool.top_candidate()

    # Priority 1: confidence threshold hit
    if top_score >= threshold:
        logger.info(
            "Confidence threshold reached: %.4f >= %.2f after %d questions.",
            top_score, threshold, questions_asked,
        )
        return ConfidenceResult(
            should_guess=True,
            reason=GuessReason.CONFIDENCE,
            top_score=top_score,
            questions_asked=questions_asked,
        )

    # Priority 2: max questions exhausted
    if questions_asked >= max_questions:
        logger.info(
            "Max questions (%d) reached. Top score: %.4f. Forcing guess.",
            max_questions, top_score,
        )
        return ConfidenceResult(
            should_guess=True,
            reason=GuessReason.MAX_QUESTIONS,
            top_score=top_score,
            questions_asked=questions_asked,
        )

    # Keep playing
    logger.debug(
        "Continue playing: top_score=%.4f, questions=%d/%d",
        top_score, questions_asked, max_questions,
    )
    return ConfidenceResult(
        should_guess=False,
        reason=GuessReason.NOT_YET,
        top_score=top_score,
        questions_asked=questions_asked,
    )
