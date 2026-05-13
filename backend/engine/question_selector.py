"""
engine/question_selector.py

Entropy-based question selection — picks the attribute that will give the
maximum information gain, splitting the candidate pool as evenly as possible.

Core idea: the best question is the one where ~50% of candidates (by score)
would answer YES and ~50% would answer NO. This maximizes Shannon entropy
and eliminates the most candidates per question on average.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.models.player import ATTRIBUTE_NAMES, ATTRIBUTE_TO_CATEGORY

if TYPE_CHECKING:
    from backend.engine.candidate_pool import CandidatePool

logger = logging.getLogger(__name__)

# Maximum questions allowed per game
MAX_QUESTIONS = 12

# Entropy of a perfect 50/50 binary split (log2(2) = 1.0)
PERFECT_ENTROPY = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AttributeScore:
    """Holds entropy metadata for a candidate attribute."""
    attribute: str
    entropy: float
    p_yes: float       # weighted probability of YES across candidates
    category: str      # semantic category (for diversity mechanism)

    def __repr__(self) -> str:
        return (
            f"AttributeScore(attr={self.attribute!r}, "
            f"entropy={self.entropy:.4f}, p_yes={self.p_yes:.3f})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entropy functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_entropy(p_yes: float) -> float:
    """
    Calculate Shannon binary entropy for a question with probability p_yes of YES.

    H(p) = -(p × log2(p)) - ((1-p) × log2(1-p))

    Returns a value in [0.0, 1.0]:
      - 1.0  → perfect 50/50 split (maximum information gain)
      - 0.0  → all candidates answer the same way (useless question)

    Edge cases: p=0 or p=1 return 0.0 (no uncertainty → no information gain).
    """
    # Clamp to avoid log(0) domain errors
    p = max(min(p_yes, 1.0 - 1e-10), 1e-10)
    q = 1.0 - p
    return -(p * math.log2(p)) - (q * math.log2(q))


def score_attribute(pool: "CandidatePool", attribute: str) -> AttributeScore:
    """
    Score a single attribute based on how well it splits the candidate pool.

    p_yes = weighted average of attribute value across all candidates
            (weights = current posterior scores, which sum to 1.0)

    Parameters
    ----------
    pool : CandidatePool
        Current candidate pool with up-to-date scores.
    attribute : str
        The attribute to evaluate.

    Returns
    -------
    AttributeScore with entropy value and metadata.
    """
    p_yes = pool.get_weighted_attribute_average(attribute)
    entropy = calculate_entropy(p_yes)
    category = ATTRIBUTE_TO_CATEGORY.get(attribute, "unknown")

    return AttributeScore(
        attribute=attribute,
        entropy=entropy,
        p_yes=p_yes,
        category=category,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Question selector
# ─────────────────────────────────────────────────────────────────────────────

def select_best_attribute(
    pool: "CandidatePool",
    asked_attributes: list[str],
    recent_categories: list[str] | None = None,
    diversity_window: int = 2,
) -> AttributeScore:
    """
    Select the best attribute to ask next, maximizing entropy while
    enforcing category diversity.

    Algorithm
    ---------
    1. Score all unused attributes by entropy.
    2. If the top attribute's category has appeared in the last
       `diversity_window` questions, try to pick from a different category.
    3. Return the best attribute (closest entropy to 1.0).

    Parameters
    ----------
    pool : CandidatePool
        Current candidate pool.
    asked_attributes : list[str]
        Attributes already asked this session (excluded from selection).
    recent_categories : list[str] | None
        Categories of the last N asked attributes (for diversity).
        If None, diversity enforcement is skipped.
    diversity_window : int
        How many recent categories to consider when enforcing diversity.

    Returns
    -------
    AttributeScore
        The best attribute to ask next, with its entropy and metadata.

    Raises
    ------
    RuntimeError
        If all attributes have already been asked.
    """
    asked_set = set(asked_attributes)
    available = [a for a in ATTRIBUTE_NAMES if a not in asked_set]

    if not available:
        raise RuntimeError(
            "All attributes have been asked. Cannot select next question."
        )

    # Score all available attributes
    scored: list[AttributeScore] = [
        score_attribute(pool, attr) for attr in available
    ]

    # Diversity enforcement: Apply an entropy penalty to categories used recently.
    # We apply a dampening factor to the entropy score if the category is in the recent set.
    # Distance from perfect entropy (1.0) is our sorting key.
    
    recent_category_counts = {}
    if recent_categories:
        # Weigh most recent categories more heavily
        for i, cat in enumerate(reversed(recent_categories[-diversity_window:])):
            weight = 1.0 / (i + 1)
            recent_category_counts[cat] = recent_category_counts.get(cat, 0) + weight

    def get_adjusted_score(s: AttributeScore) -> float:
        penalty = recent_category_counts.get(s.category, 0) * 0.2  # 20% penalty per recent use
        # Adjust entropy downwards (make it look further from 1.0)
        adjusted_entropy = s.entropy - penalty
        return abs(adjusted_entropy - PERFECT_ENTROPY)

    # Sort by adjusted distance from perfect entropy
    scored.sort(key=get_adjusted_score)

    best = scored[0]
    logger.debug("Selected attribute: %s (Category: %s)", best.attribute, best.category)
    return best


def rank_all_attributes(
    pool: "CandidatePool",
    asked_attributes: list[str],
) -> list[AttributeScore]:
    """
    Return all unused attributes ranked by entropy descending.
    Useful for debugging and the explainability sidebar.
    """
    asked_set = set(asked_attributes)
    available = [a for a in ATTRIBUTE_NAMES if a not in asked_set]
    scored = [score_attribute(pool, attr) for attr in available]
    scored.sort(key=lambda s: abs(s.entropy - PERFECT_ENTROPY))
    return scored
