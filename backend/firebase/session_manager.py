"""
firebase/session_manager.py

CRUD operations for game sessions in Firestore.
Each session is a document in /sessions/{session_id}.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.firebase.firestore_client import get_db
from backend.models.session import SessionState, SessionStatus, TurnRecord

logger = logging.getLogger(__name__)


def _sessions():
    return get_db().collection("sessions")


def create_session() -> SessionState:
    """Create a new session document and return its initial state."""
    session_id = str(uuid.uuid4())
    state = SessionState(session_id=session_id)
    _sessions().document(session_id).set(state.to_dict())
    logger.info("Session created: %s", session_id)
    return state


def get_session(session_id: str) -> SessionState:
    """Fetch and deserialize a session from Firestore."""
    doc = _sessions().document(session_id).get()
    if not doc.exists:
        raise KeyError(f"Session not found: {session_id}")
    return SessionState.from_dict(doc.to_dict())


def save_session(state: SessionState) -> None:
    """Persist the full session state to Firestore."""
    state.updated_at = datetime.now(timezone.utc).isoformat()
    _sessions().document(state.session_id).set(state.to_dict())
    logger.debug("Session saved: %s (turn %d)", state.session_id, state.questions_asked)


def append_turn(session_id: str, turn: TurnRecord, scores_snapshot: list[dict]) -> SessionState:
    """
    Add a completed turn to the session and update scores snapshot.
    Returns the updated SessionState.
    """
    state = get_session(session_id)
    state.add_turn(turn)
    state.scores_snapshot = scores_snapshot
    save_session(state)
    return state


def close_session(
    session_id: str,
    guessed_player: str,
    final_confidence: float,
) -> SessionState:
    """Mark a session as complete with the final guess."""
    state = get_session(session_id)
    state.status = SessionStatus.COMPLETE
    state.guessed_player = guessed_player
    state.final_confidence = final_confidence
    save_session(state)
    logger.info("Session closed: %s → guess=%s (%.2f)", session_id, guessed_player, final_confidence)
    return state


def log_feedback(
    session_id: str,
    guessed_player: str,
    correct_player: str,
    was_correct: bool,
    full_trace: list[dict],
) -> None:
    """Log feedback to /feedback/{session_id} collection."""
    db = get_db()
    db.collection("feedback").document(session_id).set({
        "session_id": session_id,
        "guessed_player": guessed_player,
        "correct_player": correct_player,
        "was_correct": was_correct,
        "full_trace": full_trace,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(
        "Feedback logged: session=%s guessed=%s correct=%s",
        session_id, guessed_player, correct_player,
    )
