"""
gemini/revealer.py

Prompt C — Final Reveal Generator
Model: Gemini 2.5 Flash

Given the guessed player name and the full Q&A trace,
generates a dramatic, cricket-flavored reveal paragraph.

Called exactly once per game, after confidence threshold is hit.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Model config
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_NAME = "gemini-2.5-flash"

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reveal_text": {"type": "string"},
        "fun_fact": {"type": "string"},
        "confidence_explanation": {"type": "string"},
    },
    "required": ["reveal_text", "fun_fact", "confidence_explanation"],
}

_SYSTEM_PROMPT = """You are an electrifying IPL cricket game show host revealing the mystery player.

Write a dramatic, exciting reveal for an Akinator-style IPL player guessing game.

Rules:
1. Be theatrical and exciting — like a stadium announcement
2. Reference 1-2 specific clues from the Q&A history that clinched the guess
3. Include a surprising/fun cricket fact about the player
4. Keep the reveal_text under 3 sentences — punchy, not long
5. The fun_fact should be something not obvious from the Q&A
6. confidence_explanation should briefly explain how the AI figured it out (1 sentence, judge-friendly)

Tone: Think IPL commentary — energetic, cricket-literate, celebratory.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RevealResult:
    player_name: str
    reveal_text: str
    fun_fact: str
    confidence_explanation: str
    final_confidence: float
    questions_asked: int

    def __repr__(self) -> str:
        return f"RevealResult(player={self.player_name!r}, q={self.questions_asked})"


# ─────────────────────────────────────────────────────────────────────────────
# Revealer
# ─────────────────────────────────────────────────────────────────────────────

class PlayerRevealer:
    """
    Generates the dramatic end-of-game reveal using Gemini Flash.

    Usage
    -----
    revealer = PlayerRevealer()
    result = revealer.reveal(
        player_name="MS Dhoni",
        qa_trace=[{"question": "...", "answer": "YES"}, ...],
        final_confidence=0.92,
        questions_asked=7,
    )
    print(result.reveal_text)
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set.")
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.9,  # creative for drama
                max_output_tokens=512,
            ),
        )
        # Load verified facts
        self._facts_path = os.path.join(os.path.dirname(__file__), "..", "data", "player_facts.json")
        self._player_facts = {}
        try:
            with open(self._facts_path, "r") as f:
                facts_data = json.load(f)
                # Map player_id -> list of facts
                for entry in facts_data:
                    self._player_facts[entry["player_id"]] = entry["facts"]
            logger.info("Loaded facts for %d players.", len(self._player_facts))
        except Exception as e:
            logger.error("Could not load player_facts.json: %s", e)

        logger.info("PlayerRevealer initialized with model: %s", _MODEL_NAME)

    def _get_random_fact(self, player_id: str) -> str:
        import random
        facts = self._player_facts.get(player_id)
        if facts and len(facts) > 0:
            return random.choice(facts)
        return "One of IPL's finest players."

    def reveal(
        self,
        player_name: str,
        player_id: str,
        qa_trace: list[dict],
        final_confidence: float,
        questions_asked: int,
        reason: str = "confidence",
    ) -> RevealResult:
        """
        Generate a dramatic reveal paragraph for the guessed player.

        Parameters
        ----------
        player_name : str
            The guessed player's full name.
        player_id : str
            The unique ID of the player (used to look up facts).
        qa_trace : list[dict]
            Full Q&A history: [{"question": str, "answer": str, "attribute": str}, ...]
        final_confidence : float
            The top candidate's final posterior probability (0.0–1.0).
        questions_asked : int
            Total number of questions asked this game.
        reason : str
            "confidence" or "max_questions" — affects reveal tone.

        Returns
        -------
        RevealResult
            Structured reveal with dramatic text, fun fact, and AI explanation.
        """
        # Format Q&A trace for the prompt
        trace_lines = [
            f"  Q{i+1}: {turn['question']} → {turn['answer']}"
            for i, turn in enumerate(qa_trace)
        ]
        trace_text = "\n".join(trace_lines)

        confidence_pct = f"{final_confidence:.0%}"
        trigger_note = (
            f"The AI reached {confidence_pct} confidence after {questions_asked} questions."
            if reason == "confidence"
            else f"The AI used all {questions_asked} questions and is making its best guess ({confidence_pct} confident)."
        )

        prompt = (
            f"Mystery player: {player_name}\n\n"
            f"Q&A trace:\n{trace_text}\n\n"
            f"{trigger_note}\n\n"
            f"Generate the dramatic reveal!"
        )

        # Get verified fun fact locally
        verified_fact = self._get_random_fact(player_id)

        try:
            response = self._model.generate_content(prompt)
            data = json.loads(response.text)

            result = RevealResult(
                player_name=player_name,
                reveal_text=data["reveal_text"],
                fun_fact=verified_fact, # Use our verified one!
                confidence_explanation=data["confidence_explanation"],
                final_confidence=final_confidence,
                questions_asked=questions_asked,
            )
            logger.info("Reveal generated for player: %s", player_name)
            return result

        except Exception as exc:
            logger.error("Revealer error: %s", exc)
            return RevealResult(
                player_name=player_name,
                reveal_text=f"🏏 It's {player_name}! The AI figured it out!",
                fun_fact=verified_fact,
                confidence_explanation=f"Bayesian reasoning with {questions_asked} questions.",
                final_confidence=final_confidence,
                questions_asked=questions_asked,
            )
