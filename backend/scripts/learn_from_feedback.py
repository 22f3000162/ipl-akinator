"""
scripts/learn_from_feedback.py

The "Learning Loop" — processes user feedback to improve player attribute vectors.
If the AI guessed wrong, it analyzes which questions led it astray and 
nudges the correct player's attributes to be more accurate.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
PLAYERS_JSON = BASE_DIR / "data" / "players.json"

def learn():
    """
    Simulated learning loop. 
    In a real system, this would pull from Firestore.
    For the hackathon, we demonstrate the logic of nudging attributes.
    """
    if not PLAYERS_JSON.exists():
        logger.error("players.json not found.")
        return

    with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
        players = json.load(f)

    # Create a lookup map
    player_map = {p["name"]: p for p in players}

    # Simulated feedback entries (representing what would be in Firestore)
    # This demonstrates the AI reasoning: "The user said YES to is_finisher for Rohit, 
    # but my data had 0.2. I should nudge it up."
    feedback_entries = [
        {
            "guessed_player": "Virat Kohli",
            "correct_player": "Rohit Sharma",
            "was_correct": False,
            "full_trace": [
                {"attribute": "is_finisher", "answer": "YES"},
                {"attribute": "played_mi", "answer": "YES"},
                {"attribute": "is_captain", "answer": "YES"}
            ]
        }
    ]

    learning_rate = 0.1
    changes_made = 0

    for entry in feedback_entries:
        correct_name = entry["correct_player"]
        if correct_name not in player_map:
            logger.warning(f"Correct player '{correct_name}' not in dataset. Skipping.")
            continue

        player = player_map[correct_name]
        logger.info(f"Learning for player: {correct_name}")

        for turn in entry["full_trace"]:
            attr = turn["attribute"]
            ans = turn["answer"]
            
            if attr not in player["attributes"]:
                continue

            current_val = player["attributes"][attr]
            target_val = 1.0 if ans == "YES" else 0.0 if ans == "NO" else 0.5
            
            # Nudge the value towards the user's answer
            new_val = current_val + (target_val - current_val) * learning_rate
            player["attributes"][attr] = round(new_val, 3)
            
            if abs(new_val - current_val) > 0.01:
                logger.info(f"  Nudged '{attr}': {current_val} -> {player['attributes'][attr]}")
                changes_made += 1

    if changes_made > 0:
        with open(PLAYERS_JSON, "w", encoding="utf-8") as f:
            json.dump(players, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Successfully updated dataset with {changes_made} nudges.")
    else:
        logger.info("No significant changes needed.")

if __name__ == "__main__":
    learn()
