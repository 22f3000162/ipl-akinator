"""
models/schemas.py

Pydantic request/response schemas for all FastAPI endpoints.
These are the HTTP contracts — separate from internal dataclasses.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Shared sub-models
# ─────────────────────────────────────────────────────────────────────────────

class CandidateInfo(BaseModel):
    """Top-N candidate snapshot for the frontend probability bar."""
    name: str
    score: float = Field(..., ge=0.0, le=1.0)
    player_id: str


class TurnSummary(BaseModel):
    """Condensed turn info for the frontend (excludes internal details)."""
    turn_number: int
    question: str
    reasoning: str
    answer: str
    top_candidate: str
    top_score: float


# ─────────────────────────────────────────────────────────────────────────────
# /game/start
# ─────────────────────────────────────────────────────────────────────────────

class StartGameResponse(BaseModel):
    session_id: str
    question: str
    reasoning: str
    attribute: str
    question_number: int = 1
    total_players: int
    entropy: float | None = None
    top3: list[CandidateInfo]
    top_confidence: float
    is_ai_fallback: bool = False

# ─────────────────────────────────────────────────────────────────────────────
# /game/answer
# ─────────────────────────────────────────────────────────────────────────────

class AnswerRequest(BaseModel):
    session_id: str
    raw_answer: str = Field(..., min_length=1, max_length=500)


class AnswerResponse(BaseModel):
    session_id: str
    question_number: int
    # Next question (None if game is over)
    next_question: str | None = None
    next_reasoning: str | None = None
    next_attribute: str | None = None
    entropy: float | None = None
    # Interpretation of user's answer
    interpreted_answer: str
    interpret_confidence: float
    is_ai_fallback: bool = False
    # Current state
    top3: list[CandidateInfo]
    top_confidence: float
    # Game over?
    done: bool
    guess_reason: str | None = None   # "confidence" | "max_questions" | None


# ─────────────────────────────────────────────────────────────────────────────
# /game/guess  (called when done=True)
# ─────────────────────────────────────────────────────────────────────────────

class GuessResponse(BaseModel):
    session_id: str
    player_name: str
    player_id: str
    final_confidence: float
    questions_asked: int
    reveal_text: str
    fun_fact: str
    confidence_explanation: str
    full_trace: list[TurnSummary]


# ─────────────────────────────────────────────────────────────────────────────
# /feedback/submit
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    session_id: str
    guessed_player: str
    correct_player: str
    was_correct: bool


class FeedbackResponse(BaseModel):
    success: bool
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Error responses
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
