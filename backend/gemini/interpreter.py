"""
gemini/interpreter.py

Prompt B — Response Interpreter
Model: Gemini 2.5 Flash-Lite

Takes the user's raw free-text answer + the question that was asked,
and maps it to a canonical Answer enum: YES / NO / MAYBE / DONT_KNOW.

This is the cheapest and fastest Gemini call in the pipeline (~50ms).
Uses strict JSON schema to guarantee parseable output.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import google.generativeai as genai
from dotenv import load_dotenv

from backend.engine.reasoning import Answer

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Model config
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_NAME = "gemini-2.5-flash-lite"  # cheapest, fastest; ideal for classification

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["YES", "NO", "MAYBE", "DONT_KNOW"],
        },
        "confidence": {
            "type": "number",
        },
        "reasoning": {
            "type": "string",
        },
    },
    "required": ["intent", "confidence", "reasoning"],
}

_SYSTEM_PROMPT = """You are an answer classifier for an IPL cricket guessing game.

The user was asked a yes/no question about an IPL cricketer they are thinking of.
Your job is to classify their free-text response into exactly one of four categories:

- YES: The user confirms the cricketer has this trait
- NO: The user denies the cricketer has this trait  
- MAYBE: The user is uncertain, partially agrees, or gives a qualified answer
- DONT_KNOW: The user has no information, skips, or the answer is completely unclear

Be liberal with MAYBE — if someone says "kind of", "I think so", "not sure but probably", classify as MAYBE.
Be strict about DONT_KNOW — only use it when the user genuinely has no idea or skips.

Return JSON with: intent (enum), confidence (0.0-1.0 how certain you are of your classification), reasoning (one sentence explanation).
"""


# ─────────────────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InterpretedAnswer:
    intent: Answer
    confidence: float
    reasoning: str
    raw_response: str
    is_fallback: bool = False

    def __repr__(self) -> str:
        return (
            f"InterpretedAnswer("
            f"intent={self.intent.value}, "
            f"confidence={self.confidence:.2f}, "
            f"reasoning={self.reasoning!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Interpreter
# ─────────────────────────────────────────────────────────────────────────────

class AnswerInterpreter:
    """
    Interprets free-text user answers using Gemini Flash-Lite.

    Usage
    -----
    interpreter = AnswerInterpreter()
    result = interpreter.interpret("yes he played for MI", "Did this player play for Mumbai Indians?")
    # InterpretedAnswer(intent=YES, confidence=0.97, ...)
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY not set. Add it to your .env file."
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.1,  # near-deterministic for classification
                max_output_tokens=128,
            ),
        )
        logger.info("AnswerInterpreter initialized with model: %s", _MODEL_NAME)

    def interpret(self, raw_answer: str, question_asked: str) -> InterpretedAnswer:
        """
        Classify a user's raw answer into YES/NO/MAYBE/DONT_KNOW.

        Parameters
        ----------
        raw_answer : str
            The user's free-text response (e.g. "yeah I think so").
        question_asked : str
            The question that was asked (context for classification).

        Returns
        -------
        InterpretedAnswer
            Typed result with intent enum, confidence, and reasoning.
        """
        if not raw_answer or not raw_answer.strip():
            logger.warning("Empty answer received — defaulting to DONT_KNOW.")
            return InterpretedAnswer(
                intent=Answer.DONT_KNOW,
                confidence=1.0,
                reasoning="Empty answer provided.",
                raw_response=raw_answer,
            )

        # ── Shortcut: Exact matches for buttons to save AI quota ──────────────────
        clean_ans = raw_answer.strip().lower()
        mapping = {
            "yes": Answer.YES,
            "no": Answer.NO,
            "maybe": Answer.MAYBE,
            "don't know": Answer.DONT_KNOW,
            "dont know": Answer.DONT_KNOW,
            "idk": Answer.DONT_KNOW
        }
        
        if clean_ans in mapping:
            return InterpretedAnswer(
                intent=mapping[clean_ans],
                confidence=1.0,
                reasoning=f"Exact match shortcut: '{raw_answer}'",
                raw_response=raw_answer,
                is_fallback=False  # This is a feature, not a failure
            )

        prompt = (
            f"Question asked: {question_asked}\n"
            f"User's answer: {raw_answer}"
        )

        try:
            response = self._model.generate_content(prompt)
            data = json.loads(response.text)

            intent_str = data.get("intent", "DONT_KNOW").upper()
            try:
                intent = Answer(intent_str)
            except ValueError:
                logger.warning("Unexpected intent value: %r — defaulting to DONT_KNOW", intent_str)
                intent = Answer.DONT_KNOW

            result = InterpretedAnswer(
                intent=intent,
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
                raw_response=raw_answer,
            )
            logger.debug("Interpreted: %s", result)
            return result

        except Exception as exc:
            is_quota_issue = "429" in str(exc) or "quota" in str(exc).lower()
            logger.error("Gemini interpreter error: %s (is_quota=%s) — attempting local keyword fallback", exc, is_quota_issue)
            
            # Local keyword fallback for reliability during rate-limits
            lower_ans = raw_answer.lower().strip()
            
            yes_words = {'yes', 'yeah', 'yep', 'yup', 'correct', 'true', 'definitely', 'sure'}
            no_words = {'no', 'nope', 'nah', 'false', 'never', 'wrong'}
            maybe_words = {'maybe', 'perhaps', 'might', 'not sure', 'probably', 'kind of'}
            
            if any(word in lower_ans for word in yes_words):
                intent = Answer.YES
                reasoning = "Local fallback: matched YES keywords."
            elif any(word in lower_ans for word in no_words):
                intent = Answer.NO
                reasoning = "Local fallback: matched NO keywords."
            elif any(word in lower_ans for word in maybe_words):
                intent = Answer.MAYBE
                reasoning = "Local fallback: matched MAYBE keywords."
            else:
                intent = Answer.DONT_KNOW
                reasoning = f"Local fallback: no match, defaulting to DONT_KNOW. (Original error: {exc})"
                
            return InterpretedAnswer(
                intent=intent,
                confidence=0.5, # Lower confidence for fallback
                reasoning=reasoning,
                raw_response=raw_answer,
                is_fallback=is_quota_issue,
            )
