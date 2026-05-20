"""
llm/revealer.py

Prompt C — Final Reveal Generator
Model: Configurable via LLMClient

Generates a dramatic, cricket-flavored reveal paragraph.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from backend.llm.client import LLMClient

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Default config
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_MODEL = os.getenv("LLM_MODEL")

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
6. confidence_explanation should briefly explain how the AI figured it out (1 sentence)

Tone: Think IPL commentary — energetic, cricket-literate, celebratory.
"""


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


class PlayerRevealer:
    """
    Generates the dramatic end-of-game reveal.
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()
        self._model = _DEFAULT_MODEL
        
        # Load verified facts
        self._facts_path = os.path.join(os.path.dirname(__file__), "..", "data", "player_facts.json")
        self._player_facts = {}
        try:
            with open(self._facts_path, "r") as f:
                facts_data = json.load(f)
                for entry in facts_data:
                    self._player_facts[entry["player_id"]] = entry["facts"]
            logger.info("Loaded facts for %d players.", len(self._player_facts))
        except Exception as e:
            logger.error("Could not load player_facts.json: %s", e)

        logger.info("PlayerRevealer initialized with model: %s", self._model or "provider-default")

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
        """
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

        verified_fact = self._get_random_fact(player_id)

        try:
            data = self._client.generate_json(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=prompt,
                model=self._model,
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.9,
                max_tokens=512
            )

            return RevealResult(
                player_name=player_name,
                reveal_text=data["reveal_text"],
                fun_fact=verified_fact,
                confidence_explanation=data["confidence_explanation"],
                final_confidence=final_confidence,
                questions_asked=questions_asked,
            )

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
