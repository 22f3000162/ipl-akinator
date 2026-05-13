"""
scripts/test_engine.py

CLI game loop using 50 synthetic players — validates Phase 1 with no API calls.
Run: python -m backend.scripts.test_engine
"""

from __future__ import annotations

import random
import math
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.player import Player, ATTRIBUTE_NAMES
from backend.engine.candidate_pool import CandidatePool
from backend.engine.reasoning import Answer, bayesian_update
from backend.engine.question_selector import select_best_attribute
from backend.engine.confidence import check_confidence, CONFIDENCE_THRESHOLD, MAX_QUESTIONS

# ─────────────────────────────────────────────────────────────────────────────
# Synthetic player generation
# ─────────────────────────────────────────────────────────────────────────────

FAKE_PLAYERS = [
    "Rohit Sharma", "Virat Kohli", "MS Dhoni", "Jasprit Bumrah", "Hardik Pandya",
    "Suryakumar Yadav", "KL Rahul", "Ravindra Jadeja", "Shubman Gill", "Mohammed Shami",
    "Rishabh Pant", "Shreyas Iyer", "Yuzvendra Chahal", "David Warner", "AB de Villiers",
    "Chris Gayle", "Lasith Malinga", "Kieron Pollard", "Dwayne Bravo", "Suresh Raina",
    "Gautam Gambhir", "Yusuf Pathan", "Ambati Rayudu", "Dinesh Karthik", "Robin Uthappa",
    "Brendon McCullum", "Adam Gilchrist", "Shane Watson", "Jacques Kallis", "Michael Hussey",
    "Yuvraj Singh", "Sourav Ganguly", "VVS Laxman", "Rahul Dravid", "Harbhajan Singh",
    "Anil Kumble", "Zaheer Khan", "Ajinkya Rahane", "Cheteshwar Pujara", "Wriddhiman Saha",
    "Ishan Kishan", "Deepak Chahar", "Bhuvneshwar Kumar", "Trent Boult", "Pat Cummins",
    "Kane Williamson", "Faf du Plessis", "Quinton de Kock", "Heinrich Klaasen", "Tim David",
]


def make_synthetic_player(name: str, seed: int) -> Player:
    """Generate a player with deterministic random float attributes."""
    rng = random.Random(seed)
    attrs = {attr: round(rng.uniform(0.0, 1.0), 3) for attr in ATTRIBUTE_NAMES}
    return Player(
        player_id=name.lower().replace(" ", "-"),
        name=name,
        attributes=attrs,
        nationality="Indian" if rng.random() > 0.35 else "Overseas",
    )


def generate_synthetic_pool() -> tuple[list[Player], Player]:
    """Generate 50 synthetic players, return (players, secret_target)."""
    players = [make_synthetic_player(name, i) for i, name in enumerate(FAKE_PLAYERS)]
    target = random.choice(players)
    return players, target


# ─────────────────────────────────────────────────────────────────────────────
# Auto-answer simulator (replaces real user + Gemini)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_answer(target: Player, attribute: str, noise: float = 0.1) -> Answer:
    """
    Simulate a user answer based on the target player's true attribute value.
    Adds noise to simulate realistic fuzzy answers.
    """
    val = target.get_attribute(attribute)
    r = random.random()

    # Inject noise: sometimes answer incorrectly
    if r < noise:
        return random.choice([Answer.MAYBE, Answer.DONT_KNOW])

    if val >= 0.65:
        return Answer.YES
    elif val <= 0.35:
        return Answer.NO
    else:
        return Answer.MAYBE


# ─────────────────────────────────────────────────────────────────────────────
# Verification checks
# ─────────────────────────────────────────────────────────────────────────────

def assert_scores_sum_to_one(pool: CandidatePool, turn: int) -> None:
    scores = pool.get_all_scores()
    total = sum(scores.values())
    assert abs(total - 1.0) < 1e-6, (
        f"Turn {turn}: Scores do not sum to 1.0 (got {total:.8f})"
    )


def print_top3(pool: CandidatePool) -> None:
    print("  Top 3 candidates:")
    for i, (player, score) in enumerate(pool.top_n(3), 1):
        bar = "█" * int(score * 40)
        print(f"    {i}. {player.name:<25} {score:.4f}  {bar}")


# ─────────────────────────────────────────────────────────────────────────────
# Main game loop
# ─────────────────────────────────────────────────────────────────────────────

def run_game(verbose: bool = True) -> dict:
    """
    Run one complete simulated game and return a result summary.
    """
    random.seed()  # fresh seed each run
    players, target = generate_synthetic_pool()
    pool = CandidatePool(players)

    asked_attributes: list[str] = []
    recent_categories: list[str] = []
    turns: list[dict] = []

    if verbose:
        print(f"\n{'═'*60}")
        print(f"  🏏  IPL AKINATOR — ENGINE TEST")
        print(f"{'═'*60}")
        print(f"  Secret player: {target.name}")
        print(f"  Pool size:     {len(pool)} players")
        print(f"  Max questions: {MAX_QUESTIONS}")
        print(f"  Threshold:     {CONFIDENCE_THRESHOLD:.0%}")
        print(f"{'─'*60}\n")

    # Validate initial state
    assert_scores_sum_to_one(pool, 0)

    for turn_num in range(1, MAX_QUESTIONS + 1):
        # 1. Pick best attribute
        attr_score = select_best_attribute(pool, asked_attributes, recent_categories)
        attribute = attr_score.attribute

        # 2. Simulate user answer
        answer = simulate_answer(target, attribute)

        # 3. Bayesian update
        bayesian_update(pool, attribute, answer)
        assert_scores_sum_to_one(pool, turn_num)

        # 4. Track state
        asked_attributes.append(attribute)
        recent_categories.append(attr_score.category)
        top_player, top_score = pool.top_candidate()

        turns.append({
            "turn": turn_num,
            "attribute": attribute,
            "category": attr_score.category,
            "entropy": round(attr_score.entropy, 4),
            "answer": answer.value,
            "top_player": top_player.name,
            "top_score": round(top_score, 4),
        })

        if verbose:
            print(f"Turn {turn_num:2d} | {attribute:<30} | entropy={attr_score.entropy:.3f} | answer={answer.value:<9} | top={top_player.name} ({top_score:.3f})")
            if turn_num % 3 == 0:
                print_top3(pool)
                print()

        # 5. Confidence check
        result = check_confidence(pool, turn_num)
        if result.should_guess:
            guessed_player, guessed_score = pool.top_candidate()
            correct = guessed_player.player_id == target.player_id

            if verbose:
                print(f"\n{'─'*60}")
                print(f"  🎯  GUESS: {guessed_player.name} ({guessed_score:.2%} confidence)")
                print(f"  🏏  TARGET: {target.name}")
                print(f"  ✅  CORRECT: {correct}")
                print(f"  📊  REASON: {result.reason.value}")
                print(f"  🔢  Questions asked: {turn_num}")
                print(f"{'═'*60}\n")

            return {
                "target": target.name,
                "guess": guessed_player.name,
                "correct": correct,
                "questions_asked": turn_num,
                "final_score": guessed_score,
                "reason": result.reason.value,
                "turns": turns,
            }

    # Fallback (should not reach here due to MAX_QUESTIONS check in loop)
    guessed_player, guessed_score = pool.top_candidate()
    return {
        "target": target.name,
        "guess": guessed_player.name,
        "correct": guessed_player.player_id == target.player_id,
        "questions_asked": MAX_QUESTIONS,
        "final_score": guessed_score,
        "reason": "max_questions",
        "turns": turns,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Multi-game stats
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark(n_games: int = 20) -> None:
    """Run N games and print aggregate stats."""
    print(f"\nRunning {n_games}-game benchmark...\n")
    results = [run_game(verbose=False) for _ in range(n_games)]

    correct = sum(1 for r in results if r["correct"])
    avg_q = sum(r["questions_asked"] for r in results) / n_games
    avg_conf = sum(r["final_score"] for r in results) / n_games
    conf_triggered = sum(1 for r in results if r["reason"] == "confidence")

    print(f"{'═'*50}")
    print(f"  BENCHMARK RESULTS ({n_games} games)")
    print(f"{'─'*50}")
    print(f"  Accuracy:            {correct}/{n_games} ({correct/n_games:.0%})")
    print(f"  Avg questions/game:  {avg_q:.1f} / {MAX_QUESTIONS}")
    print(f"  Avg final confidence:{avg_conf:.2%}")
    print(f"  Confidence triggers: {conf_triggered}/{n_games}")
    print(f"  Max-Q triggers:      {n_games - conf_triggered}/{n_games}")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    # Single verbose game
    run_game(verbose=True)

    # Benchmark
    run_benchmark(n_games=20)
