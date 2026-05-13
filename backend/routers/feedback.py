"""
routers/feedback.py

POST /feedback/submit — log user correction when the AI guessed wrong.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.firebase.session_manager import log_feedback, get_session
from backend.models.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(req: FeedbackRequest) -> FeedbackResponse:
    """
    Record user feedback when the AI guessed incorrectly.
    Logs to /feedback/{session_id} in Firestore for the learning loop.
    """
    try:
        state = get_session(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {req.session_id}")

    full_trace = [
        {
            "question": t.question,
            "answer": t.interpreted,
            "attribute": t.attribute,
        }
        for t in state.turns
        if t.interpreted
    ]

    log_feedback(
        session_id=req.session_id,
        guessed_player=req.guessed_player,
        correct_player=req.correct_player,
        was_correct=req.was_correct,
        full_trace=full_trace,
    )

    if not req.was_correct and req.correct_player:
        from backend.engine.learning import apply_feedback_learning
        apply_feedback_learning(req.correct_player, full_trace)

    logger.info(
        "Feedback: session=%s guessed=%s correct=%s was_correct=%s",
        req.session_id, req.guessed_player, req.correct_player, req.was_correct,
    )

    return FeedbackResponse(
        success=True,
        message=(
            "Thanks! We'll use this to improve."
            if not req.was_correct
            else "Great — glad we got it right!"
        ),
    )
