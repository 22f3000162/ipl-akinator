"""
routers/game.py

Game endpoints:
  POST /game/start          → start new session, return first question
  POST /game/answer         → process answer, return next question or done signal
  GET  /game/guess/{id}     → return final guess + reveal
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.engine.candidate_pool import CandidatePool
from backend.engine.confidence import check_confidence
from backend.engine.question_selector import select_best_attribute
from backend.engine.reasoning import Answer, bayesian_update
from backend.firebase.firestore_client import get_db
from backend.firebase.session_manager import (
    close_session, create_session, get_session, save_session,
)
from backend.gemini.interpreter import AnswerInterpreter
from backend.gemini.naturalizer import QATurn, QuestionNaturalizer
from backend.gemini.revealer import PlayerRevealer
from backend.models.player import Player
from backend.models.schemas import (
    AnswerRequest, AnswerResponse, CandidateInfo,
    GuessResponse, StartGameResponse, TurnSummary,
)
from backend.models.session import TurnRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/game", tags=["game"])

# ─────────────────────────────────────────────────────────────────────────────
# Load player data once at startup
# ─────────────────────────────────────────────────────────────────────────────

_PLAYERS_PATH = Path(__file__).parent.parent / "data" / "players.json"


def _load_players() -> list[Player]:
    if not _PLAYERS_PATH.exists():
        raise RuntimeError(
            f"players.json not found at {_PLAYERS_PATH}. "
            "Run: python -m backend.scripts.generate_dataset --mode convert"
        )
    with open(_PLAYERS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return [Player.from_dict(p) for p in raw]


_ALL_PLAYERS: list[Player] = _load_players()
logger.info("Loaded %d players from players.json", len(_ALL_PLAYERS))

# ─────────────────────────────────────────────────────────────────────────────
# Lazy-init Gemini modules
# ─────────────────────────────────────────────────────────────────────────────

_interpreter: AnswerInterpreter | None = None
_naturalizer: QuestionNaturalizer | None = None
_revealer: PlayerRevealer | None = None


def get_interpreter() -> AnswerInterpreter:
    global _interpreter
    if _interpreter is None:
        _interpreter = AnswerInterpreter()
    return _interpreter


def get_naturalizer() -> QuestionNaturalizer:
    global _naturalizer
    if _naturalizer is None:
        _naturalizer = QuestionNaturalizer()
    return _naturalizer


def get_revealer() -> PlayerRevealer:
    global _revealer
    if _revealer is None:
        _revealer = PlayerRevealer()
    return _revealer


# ─────────────────────────────────────────────────────────────────────────────
# In-memory pool cache (session_id → CandidatePool)
# ─────────────────────────────────────────────────────────────────────────────

_active_pools: dict[str, CandidatePool] = {}


def _get_pool(session_id: str) -> CandidatePool:
    """Return live pool or reconstruct from committed turns (NOT pending)."""
    if session_id in _active_pools:
        return _active_pools[session_id]

    state = get_session(session_id)
    pool = CandidatePool(_ALL_PLAYERS)

    # Replay only committed (fully answered) turns
    for turn in state.turns:
        if turn.interpreted:
            try:
                bayesian_update(pool, turn.attribute, Answer(turn.interpreted))
            except Exception as e:
                logger.warning("Replay turn %d failed: %s", turn.turn_number, e)

    _active_pools[session_id] = pool
    return pool


def _top3(pool: CandidatePool) -> list[CandidateInfo]:
    return [
        CandidateInfo(name=p.name, score=round(s, 4), player_id=p.player_id)
        for p, s in pool.top_n(3)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# POST /game/start
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartGameResponse)
async def start_game() -> StartGameResponse:
    """
    Start a new game session.

    Flow:
      1. Create Firestore session
      2. Build fresh CandidatePool
      3. Pick first attribute via entropy
      4. Naturalize → question + reasoning
      5. Save pending question to session
      6. Return question to frontend
    """
    state = create_session()
    session_id = state.session_id

    pool = CandidatePool(_ALL_PLAYERS)
    _active_pools[session_id] = pool

    # Pick best first attribute
    attr_score = select_best_attribute(pool, asked_attributes=[], recent_categories=[])

    # Naturalize
    natural = get_naturalizer().naturalize(
        attribute=attr_score.attribute,
        qa_history=[],
        top5_names=[p.name for p, _ in pool.top_n(5)],
        question_number=1,
    )

    # Save pending state — this is what /answer will consume
    state.set_pending(
        attribute=attr_score.attribute,
        question=natural.question,
        reasoning=natural.reasoning,
        category=attr_score.category,
    )
    save_session(state)

    logger.info("Game started: session=%s first_attr=%s", session_id, attr_score.attribute)

    return StartGameResponse(
        session_id=session_id,
        question=natural.question,
        reasoning=natural.reasoning,
        attribute=attr_score.attribute,
        question_number=1,
        total_players=len(_ALL_PLAYERS),
        entropy=round(attr_score.entropy, 4),
        top3=_top3(pool),
        top_confidence=round(pool.top_candidate()[1], 4),
        is_ai_fallback=natural.is_fallback,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /game/answer
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/answer", response_model=AnswerResponse)
async def answer_question(req: AnswerRequest) -> AnswerResponse:
    """
    Process a user's answer.

    Flow:
      1. Load session — read pending_attribute / pending_question
      2. Interpret raw answer → YES/NO/MAYBE/DONT_KNOW  (Gemini Flash-Lite)
      3. Bayesian update on pool
      4. Commit TurnRecord to session
      5. Check confidence — if done: return done=True
      6. Pick next attribute + naturalize                (Gemini Flash)
      7. Save new pending state
      8. Return response
    """
    session_id = req.session_id

    try:
        state = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Guard: must have a pending question
    if not state.pending_attribute:
        raise HTTPException(
            status_code=400,
            detail="No pending question. Call /game/start first."
        )

    pool = _get_pool(session_id)

    # Capture pending state before we overwrite it
    current_attribute = state.pending_attribute
    current_question  = state.pending_question
    current_reasoning = state.pending_reasoning
    current_category  = state.pending_category

    # ── Step 1: Interpret ─────────────────────────────────────────────────────
    interpreted = get_interpreter().interpret(
        raw_answer=req.raw_answer,
        question_asked=current_question,
    )

    # ── Step 2: Bayesian update ───────────────────────────────────────────────
    bayesian_update(pool, current_attribute, interpreted.intent)
    top_player, top_score = pool.top_candidate()

    # ── Step 3: Commit this turn ──────────────────────────────────────────────
    turn_number = state.questions_asked + 1
    turn = TurnRecord(
        turn_number=turn_number,
        attribute=current_attribute,
        attribute_category=current_category,
        question=current_question,
        reasoning=current_reasoning,
        raw_answer=req.raw_answer,
        interpreted=interpreted.intent.value,
        interpret_confidence=interpreted.confidence,
        top_player=top_player.name,
        top_score=top_score,
    )
    state.add_turn(turn)
    state.scores_snapshot = pool.snapshot()

    # ── Step 4: Confidence check ──────────────────────────────────────────────
    confidence_result = check_confidence(pool, questions_asked=turn_number)

    if confidence_result.should_guess:
        # Clear pending — game is done
        state.set_pending("", "", "", "")
        save_session(state)

        return AnswerResponse(
            session_id=session_id,
            question_number=turn_number,
            next_question=None,
            next_reasoning=None,
            next_attribute=None,
            interpreted_answer=interpreted.intent.value,
            interpret_confidence=interpreted.confidence,
            top3=_top3(pool),
            top_confidence=round(top_score, 4),
            done=True,
            guess_reason=confidence_result.reason.value,
            entropy=None,
        )

    # ── Step 5: Pick next question ────────────────────────────────────────────
    qa_history = [
        QATurn(question=t.question, answer=t.interpreted)
        for t in state.turns
    ]
    next_attr_score = select_best_attribute(
        pool,
        asked_attributes=state.asked_attributes,
        recent_categories=state.recent_categories,
    )
    next_natural = get_naturalizer().naturalize(
        attribute=next_attr_score.attribute,
        qa_history=qa_history,
        top5_names=[p.name for p, _ in pool.top_n(5)],
        question_number=turn_number + 1,
    )

    # ── Step 6: Save new pending state ────────────────────────────────────────
    state.set_pending(
        attribute=next_attr_score.attribute,
        question=next_natural.question,
        reasoning=next_natural.reasoning,
        category=next_attr_score.category,
    )
    save_session(state)

    return AnswerResponse(
        session_id=session_id,
        question_number=turn_number,
        next_question=next_natural.question,
        next_reasoning=next_natural.reasoning,
        next_attribute=next_attr_score.attribute,
        interpreted_answer=interpreted.intent.value,
        interpret_confidence=interpreted.confidence,
        top3=_top3(pool),
        top_confidence=round(top_score, 4),
        done=False,
        guess_reason=None,
        entropy=round(next_attr_score.entropy, 4),
        is_ai_fallback=interpreted.is_fallback or next_natural.is_fallback,
    )


@router.post("/undo/{session_id}", response_model=StartGameResponse)
async def undo_turn(session_id: str) -> StartGameResponse:
    """
    Revert the last answer.
    Removes the last TurnRecord and returns the previous question state.
    """
    try:
        state = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not state.undo_last_turn():
        raise HTTPException(status_code=400, detail="Cannot undo: no turns found.")

    # Re-calculate pool from the now-truncated history
    pool = CandidatePool(_ALL_PLAYERS)
    for turn in state.turns:
        bayesian_update(pool, turn.attribute, Answer(turn.interpreted))
    
    # Update global cache
    _active_pools[session_id] = pool
    
    save_session(state)

    logger.info("Undo: session=%s restored turn=%d", session_id, state.questions_asked + 1)

    return StartGameResponse(
        session_id=session_id,
        question=state.pending_question,
        reasoning=state.pending_reasoning,
        attribute=state.pending_attribute,
        question_number=state.questions_asked + 1,
        total_players=len(_ALL_PLAYERS),
        entropy=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /game/guess/{session_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/guess/{session_id}", response_model=GuessResponse)
async def get_guess(session_id: str) -> GuessResponse:
    """
    Return final guess + dramatic Gemini reveal.
    Called by frontend when done=True is received from /game/answer.
    """
    try:
        state = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    pool = _get_pool(session_id)
    top_player, top_score = pool.top_candidate()

    qa_trace = [
        {"question": t.question, "answer": t.interpreted, "attribute": t.attribute}
        for t in state.turns
    ]

    reveal = get_revealer().reveal(
        player_name=top_player.name,
        player_id=top_player.player_id,
        qa_trace=qa_trace,
        final_confidence=top_score,
        questions_asked=state.questions_asked,
    )

    close_session(session_id, top_player.name, top_score)

    full_trace = [
        TurnSummary(
            turn_number=t.turn_number,
            question=t.question,
            reasoning=t.reasoning,
            answer=t.interpreted,
            top_candidate=t.top_player,
            top_score=t.top_score,
        )
        for t in state.turns
    ]

    return GuessResponse(
        session_id=session_id,
        player_name=top_player.name,
        player_id=top_player.player_id,
        final_confidence=round(top_score, 4),
        questions_asked=state.questions_asked,
        reveal_text=reveal.reveal_text,
        fun_fact=reveal.fun_fact,
        confidence_explanation=reveal.confidence_explanation,
        full_trace=full_trace,
    )
