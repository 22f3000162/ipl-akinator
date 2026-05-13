"""
models/session.py

Session and turn dataclasses — represent the in-memory and Firestore state
of a single game session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SessionStatus(str, Enum):
    ACTIVE   = "active"
    COMPLETE = "complete"
    ABORTED  = "aborted"


@dataclass
class TurnRecord:
    """Log entry for a single question-answer turn."""
    turn_number: int
    attribute: str
    attribute_category: str
    question: str           # naturalized question shown to user
    reasoning: str          # Gemini's reasoning (for explainability sidebar)
    raw_answer: str         # user's original free-text
    interpreted: str        # YES / NO / MAYBE / DONT_KNOW
    interpret_confidence: float
    top_player: str         # leading candidate after this turn
    top_score: float        # leading candidate's score after this turn

    def to_dict(self) -> dict:
        return {
            "turn_number": self.turn_number,
            "attribute": self.attribute,
            "attribute_category": self.attribute_category,
            "question": self.question,
            "reasoning": self.reasoning,
            "raw_answer": self.raw_answer,
            "interpreted": self.interpreted,
            "interpret_confidence": self.interpret_confidence,
            "top_player": self.top_player,
            "top_score": round(self.top_score, 6),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TurnRecord":
        return cls(**data)


@dataclass
class SessionState:
    """
    Complete state of a game session.
    Stored in Firestore at /sessions/{session_id}.

    pending_* fields track the CURRENT question that was shown to the user
    but not yet answered. On each /game/answer call these are consumed,
    a TurnRecord is committed, and the next pending_* set is saved.
    """
    session_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    turns: list[TurnRecord] = field(default_factory=list)
    asked_attributes: list[str] = field(default_factory=list)
    recent_categories: list[str] = field(default_factory=list)
    scores_snapshot: list[dict] = field(default_factory=list)
    guessed_player: str | None = None
    final_confidence: float = 0.0
    # Pending question state (set by /start and each /answer)
    pending_attribute: str = ""
    pending_question: str = ""
    pending_reasoning: str = ""
    pending_category: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def questions_asked(self) -> int:
        return len(self.turns)

    def add_turn(self, turn: TurnRecord) -> None:
        self.turns.append(turn)
        self.asked_attributes.append(turn.attribute)
        self.recent_categories.append(turn.attribute_category)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def undo_last_turn(self) -> bool:
        """
        Removes the last committed turn and restores it to pending state.
        Returns True if a turn was removed, False if no turns exist.
        """
        if not self.turns:
            return False
        
        last_turn = self.turns.pop()
        
        # Also remove from tracking lists
        if self.asked_attributes and self.asked_attributes[-1] == last_turn.attribute:
            self.asked_attributes.pop()
        if self.recent_categories and self.recent_categories[-1] == last_turn.attribute_category:
            self.recent_categories.pop()
            
        # Restore the last turn's metadata to pending so user can answer it again
        self.pending_attribute = last_turn.attribute
        self.pending_question = last_turn.question
        self.pending_reasoning = last_turn.reasoning
        self.pending_category = last_turn.attribute_category
        
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def set_pending(self, attribute: str, question: str, reasoning: str, category: str) -> None:
        self.pending_attribute = attribute
        self.pending_question = question
        self.pending_reasoning = reasoning
        self.pending_category = category
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "turns": [t.to_dict() for t in self.turns],
            "asked_attributes": self.asked_attributes,
            "recent_categories": self.recent_categories,
            "scores_snapshot": self.scores_snapshot,
            "guessed_player": self.guessed_player,
            "final_confidence": self.final_confidence,
            "pending_attribute": self.pending_attribute,
            "pending_question": self.pending_question,
            "pending_reasoning": self.pending_reasoning,
            "pending_category": self.pending_category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        turns = [TurnRecord.from_dict(t) for t in data.get("turns", [])]
        return cls(
            session_id=data["session_id"],
            status=SessionStatus(data.get("status", "active")),
            turns=turns,
            asked_attributes=data.get("asked_attributes", []),
            recent_categories=data.get("recent_categories", []),
            scores_snapshot=data.get("scores_snapshot", []),
            guessed_player=data.get("guessed_player"),
            final_confidence=data.get("final_confidence", 0.0),
            pending_attribute=data.get("pending_attribute", ""),
            pending_question=data.get("pending_question", ""),
            pending_reasoning=data.get("pending_reasoning", ""),
            pending_category=data.get("pending_category", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
