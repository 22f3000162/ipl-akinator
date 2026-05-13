"""
models/player.py

Player dataclass and ATTRIBUTE_NAMES — single source of truth for all 30 float attributes.
All attribute values are floats in [0.0, 1.0].
"""

from dataclasses import dataclass, field
from typing import Dict


# ─────────────────────────────────────────────────────────────────────────────
# Master attribute list — 30 attributes across 8 semantic categories.
# ORDER MATTERS: used as canonical key ordering throughout the system.
# ─────────────────────────────────────────────────────────────────────────────

ATTRIBUTE_NAMES: list[str] = [
    # Identity (2)
    "is_indian",
    "is_overseas",

    # Role (4)
    "is_batsman",
    "is_bowler",
    "is_allrounder",
    "is_wicketkeeper",

    # Batting style (6)
    "is_opener",
    "is_finisher",
    "is_anchor",
    "is_aggressive_batter",
    "bats_left",
    "bats_right",

    # Bowling style (6)
    "bowls_fast",
    "bowls_spin",
    "bowls_medium",
    "is_death_bowler",
    "is_powerplay_bowler",
    "is_economy_bowler",

    # Teams played for (10)
    "played_csk",
    "played_mi",
    "played_rcb",
    "played_kkr",
    "played_dc",
    "played_srh",
    "played_rr",
    "played_pbks",
    "played_gt",
    "played_lsg",

    # Achievement (5)
    "is_captain",
    "won_ipl_title",
    "has_orange_cap",
    "has_purple_cap",
    "is_international_star",

    # Era (3)
    "is_early_era",   # 2008–2012
    "is_mid_era",     # 2013–2018
    "is_recent_era",  # 2019+

    # Semantic / playstyle (4)
    "is_match_winner",
    "is_famous_for_sixes",
    "is_death_specialist",
    "is_consistent_performer",
]

# Sanity check at import time
assert len(ATTRIBUTE_NAMES) == 40, (
    f"Expected 40 attributes, got {len(ATTRIBUTE_NAMES)}. "
    "Update this assert if you intentionally change the count."
)

# Category → attribute mapping (used by question diversity mechanism)
ATTRIBUTE_CATEGORIES: Dict[str, list[str]] = {
    "identity":    ["is_indian", "is_overseas"],
    "role":        ["is_batsman", "is_bowler", "is_allrounder", "is_wicketkeeper"],
    "batting":     ["is_opener", "is_finisher", "is_anchor", "is_aggressive_batter", "bats_left", "bats_right"],
    "bowling":     ["bowls_fast", "bowls_spin", "bowls_medium", "is_death_bowler", "is_powerplay_bowler", "is_economy_bowler"],
    "teams":       ["played_csk", "played_mi", "played_rcb", "played_kkr", "played_dc",
                    "played_srh", "played_rr", "played_pbks", "played_gt", "played_lsg"],
    "achievement": ["is_captain", "won_ipl_title", "has_orange_cap", "has_purple_cap", "is_international_star"],
    "era":         ["is_early_era", "is_mid_era", "is_recent_era"],
    "semantic":    ["is_match_winner", "is_famous_for_sixes", "is_death_specialist", "is_consistent_performer"],
}

# Reverse map: attribute → category name
ATTRIBUTE_TO_CATEGORY: Dict[str, str] = {
    attr: category
    for category, attrs in ATTRIBUTE_CATEGORIES.items()
    for attr in attrs
}


# ─────────────────────────────────────────────────────────────────────────────
# Player dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Player:
    """
    Represents a single IPL player with their probabilistic attribute vector.

    Attributes
    ----------
    player_id : str
        Unique identifier (e.g., Firestore document ID or slug like "ms-dhoni").
    name : str
        Full display name of the player.
    attributes : Dict[str, float]
        Map of attribute_name → float in [0.0, 1.0].
        Must contain all keys listed in ATTRIBUTE_NAMES.
    team_history : list[str]
        Optional human-readable list of teams (for display/metadata only).
    nationality : str
        "Indian" or country name. Informational only.
    """

    player_id: str
    name: str
    attributes: Dict[str, float]
    team_history: list[str] = field(default_factory=list)
    nationality: str = "Indian"

    def __post_init__(self) -> None:
        self._validate_attributes()

    def _validate_attributes(self) -> None:
        """Ensure all required attributes are present and within [0.0, 1.0]."""
        missing = [k for k in ATTRIBUTE_NAMES if k not in self.attributes]
        if missing:
            raise ValueError(
                f"Player '{self.name}' is missing attributes: {missing}"
            )

        out_of_range = [
            (k, v) for k, v in self.attributes.items()
            if not (0.0 <= v <= 1.0)
        ]
        if out_of_range:
            raise ValueError(
                f"Player '{self.name}' has out-of-range attribute values: {out_of_range}"
            )

    def get_attribute(self, attribute: str) -> float:
        """Return the float value for the given attribute key."""
        if attribute not in self.attributes:
            raise KeyError(f"Unknown attribute: '{attribute}'")
        return self.attributes[attribute]

    def to_dict(self) -> dict:
        """Serialize to plain dict (for Firestore storage)."""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "attributes": self.attributes,
            "team_history": self.team_history,
            "nationality": self.nationality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        """Deserialize from plain dict (from Firestore)."""
        return cls(
            player_id=data["player_id"],
            name=data["name"],
            attributes=data["attributes"],
            team_history=data.get("team_history", []),
            nationality=data.get("nationality", "Indian"),
        )

    def __repr__(self) -> str:
        return f"Player(id={self.player_id!r}, name={self.name!r}, nationality={self.nationality!r})"
