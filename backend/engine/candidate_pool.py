"""
engine/candidate_pool.py

CandidatePool — manages the live scoring of all players during a game session.

Each player starts with an equal unnormalized score of 1.0.
After every Bayesian update, scores are renormalized to sum to 1.0,
making each score interpretable as a posterior probability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from backend.models.player import Player

logger = logging.getLogger(__name__)


@dataclass
class ScoredPlayer:
    """A player with its current posterior probability score."""
    player: Player
    score: float = 1.0

    def __repr__(self) -> str:
        return f"ScoredPlayer({self.player.name!r}, score={self.score:.4f})"


class CandidatePool:
    """
    Manages the complete set of IPL player candidates and their posterior scores.

    Usage
    -----
    pool = CandidatePool(players)
    pool.apply_scores({player_id: multiplier, ...})
    pool.normalize()
    top3 = pool.top_n(3)
    """

    def __init__(self, players: List[Player]) -> None:
        if not players:
            raise ValueError("CandidatePool requires at least one player.")

        self._pool: Dict[str, ScoredPlayer] = {
            p.player_id: ScoredPlayer(player=p, score=1.0)
            for p in players
        }
        # Initialize: normalize so all scores start as equal probabilities
        self.normalize()
        logger.info("CandidatePool initialized with %d players.", len(players))

    # ─────────────────────────────────────────────────────────────────────────
    # Core operations
    # ─────────────────────────────────────────────────────────────────────────

    def normalize(self) -> None:
        """
        Renormalize all scores so they sum to 1.0.
        If total is 0 (all scores zeroed out), resets to uniform distribution
        to prevent a degenerate state.
        """
        total = sum(sp.score for sp in self._pool.values())

        if total == 0.0:
            logger.warning(
                "All scores collapsed to 0. Resetting to uniform distribution. "
                "This may indicate contradictory user answers."
            )
            equal = 1.0 / len(self._pool)
            for sp in self._pool.values():
                sp.score = equal
        else:
            for sp in self._pool.values():
                sp.score /= total

    def multiply_scores(self, multipliers: Dict[str, float]) -> None:
        """
        Multiply each player's score by the given multiplier.

        Parameters
        ----------
        multipliers : Dict[player_id → multiplier_float]
            Only players in this dict are updated. Others are untouched.
        """
        for player_id, multiplier in multipliers.items():
            if player_id not in self._pool:
                logger.warning("Unknown player_id in multipliers: %s", player_id)
                continue
            self._pool[player_id].score *= multiplier

        self.normalize()

    def get_all_scores(self) -> Dict[str, float]:
        """Return {player_id: score} for all candidates."""
        return {pid: sp.score for pid, sp in self._pool.items()}

    def get_player(self, player_id: str) -> Player:
        """Return the Player object for a given ID."""
        if player_id not in self._pool:
            raise KeyError(f"Player ID not found in pool: {player_id!r}")
        return self._pool[player_id].player

    def top_n(self, n: int) -> List[Tuple[Player, float]]:
        """
        Return the top-N candidates by descending score.

        Returns
        -------
        List of (Player, score) tuples, highest score first.
        """
        sorted_pool = sorted(
            self._pool.values(),
            key=lambda sp: sp.score,
            reverse=True,
        )
        return [(sp.player, sp.score) for sp in sorted_pool[:n]]

    def top_candidate(self) -> Tuple[Player, float]:
        """Return the single highest-scored candidate and their probability."""
        tops = self.top_n(1)
        return tops[0]

    def get_weighted_attribute_average(self, attribute: str) -> float:
        """
        Compute the score-weighted average of a given attribute across all candidates.

        This is p_yes for the entropy calculation:
            p_yes = Σ (score_i × attribute_i) for all i

        Since scores are already normalized (sum to 1.0), this is just a
        weighted average.
        """
        total = 0.0
        for sp in self._pool.values():
            attr_val = sp.player.get_attribute(attribute)
            total += sp.score * attr_val
        return total

    # ─────────────────────────────────────────────────────────────────────────
    # Introspection
    # ─────────────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._pool)

    def snapshot(self) -> List[dict]:
        """
        Return a serializable snapshot of current top-10 scores.
        Used for Firestore session logging.
        """
        return [
            {"player_id": p.player_id, "name": p.name, "score": round(score, 6)}
            for p, score in self.top_n(10)
        ]

    def __repr__(self) -> str:
        top = self.top_n(3)
        top_str = ", ".join(f"{p.name}={s:.3f}" for p, s in top)
        return f"CandidatePool(n={len(self)}, top3=[{top_str}])"
