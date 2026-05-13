"""
engine/learning.py

The "Learning Loop" logic — nudges player attribute vectors based on user feedback.
This is what enables the system to "improve over time".
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
PLAYERS_JSON = BASE_DIR / "data" / "players.json"

def apply_feedback_learning(correct_player_name: str, full_trace: list[dict]):
    """
    Nudges the correct player's attributes based on user answers in a failed game.
    """
    if not PLAYERS_JSON.exists():
        logger.error("players.json not found for learning.")
        return

    try:
        with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
            players = json.load(f)

        # Create a lookup map
        player_map = {p["name"]: p for p in players}

        if correct_player_name not in player_map:
            logger.warning("Correct player '%s' not in dataset. Skipping nudge.", correct_player_name)
            return

        player = player_map[correct_player_name]
        learning_rate = 0.1
        changes_made = 0

        for turn in full_trace:
            attr = turn.get("attribute")
            ans = turn.get("answer") # This is the intent (YES/NO/MAYBE)
            
            if not attr or attr not in player["attributes"]:
                continue

            current_val = player["attributes"][attr]
            
            # Map Answer Intent to Target Probability
            if ans == "YES":
                target_val = 1.0
            elif ans == "NO":
                target_val = 0.0
            elif ans == "MAYBE":
                target_val = 0.5
            else:
                continue # Skip DONT_KNOW
            
            # Nudge the value towards the user's answer
            # If user said YES but current is 0.2, new becomes 0.2 + (1.0 - 0.2)*0.1 = 0.28
            new_val = current_val + (target_val - current_val) * learning_rate
            player["attributes"][attr] = round(new_val, 3)
            
            if abs(new_val - current_val) > 0.001:
                changes_made += 1

        if changes_made > 0:
            with open(PLAYERS_JSON, "w", encoding="utf-8") as f:
                json.dump(players, f, indent=2, ensure_ascii=False)
            logger.info("✅ Live Learning Applied: Nudged %d attributes for '%s'.", changes_made, correct_player_name)
        
    except Exception as e:
        logger.error("Learning application failed: %s", e)
