import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import QuestionCard from './components/QuestionCard'
import ProbabilityBar from './components/ProbabilityBar'
import ConfidenceMeter from './components/ConfidenceMeter'
import RevealCard from './components/RevealCard'
import FeedbackModal from './components/FeedbackModal'
import './App.css'

const API = ''  // proxied via vite.config.js

// ── Game state machine ───────────────────────────────────────────────────────
// IDLE → PLAYING → REVEALING → FEEDBACK
// ─────────────────────────────────────────────────────────────────────────────

const INITIAL_STATE = {
  phase: 'IDLE',
  sessionId: null,
  questionNumber: 1,
  question: null,
  reasoning: null,
  attribute: null,
  top3: [],
  topConfidence: 0,
  interpretedAnswer: null,
  isAiFallback: false,
  loading: false,
  error: null,
  entropy: null,
  // Reveal data
  reveal: null,
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API error')
  }
  return res.json()
}

export default function App() {
  const [state, setState] = useState(INITIAL_STATE)
  const [showFeedback, setShowFeedback] = useState(false)

  const update = (patch) => setState(s => ({ ...s, ...patch }))

  // ── Start game ─────────────────────────────────────────────────────────────
  const startGame = useCallback(async () => {
    update({ loading: true, error: null, phase: 'IDLE' })
    try {
      const data = await apiFetch('/game/start', { method: 'POST' })
      setState({
        ...INITIAL_STATE,
        phase: 'PLAYING',
        sessionId: data.session_id,
        question: data.question,
        reasoning: data.reasoning,
        attribute: data.attribute,
        entropy: data.entropy,
        questionNumber: 1,
        top3: data.top3,
        topConfidence: data.top_confidence,
        isAiFallback: data.is_ai_fallback,
        loading: false,
      })
    } catch (e) {
      update({ loading: false, error: e.message })
    }
  }, [])

  // ── Submit answer ──────────────────────────────────────────────────────────
  const submitAnswer = useCallback(async (rawAnswer) => {
    if (state.loading || !state.sessionId) return
    update({ 
      loading: true, 
      error: null,
      // Clear current turn info while loading next
      interpretedAnswer: null, 
    })

    try {
      const data = await apiFetch('/game/answer', {
        method: 'POST',
        body: JSON.stringify({ session_id: state.sessionId, raw_answer: rawAnswer }),
      })

      if (data.done) {
        // Fetch full guess+reveal
        const guessData = await apiFetch(`/game/guess/${state.sessionId}`)
        setState(s => ({
          ...s,
          phase: 'REVEALING',
          top3: data.top3,
          topConfidence: data.top_confidence,
          interpretedAnswer: data.interpreted_answer,
          loading: false,
          reveal: guessData,
        }))
      } else {
        setState(s => ({
          ...s,
          question: data.next_question,
          reasoning: data.next_reasoning,
          attribute: data.next_attribute,
          questionNumber: data.question_number + 1,
          top3: data.top3,
          topConfidence: data.top_confidence,
          interpretedAnswer: data.interpreted_answer,
          isAiFallback: data.is_ai_fallback,
          entropy: data.entropy,
          loading: false,
        }))
      }
    } catch (e) {
      update({ loading: false, error: e.message })
    }
  }, [state.loading, state.sessionId])

  // ── Submit feedback ────────────────────────────────────────────────────────
  const submitFeedback = useCallback(async (correctPlayer) => {
    await apiFetch('/feedback/submit', {
      method: 'POST',
      body: JSON.stringify({
        session_id: state.sessionId,
        guessed_player: state.reveal?.player_name ?? '',
        correct_player: correctPlayer,
        was_correct: false,
      }),
    })
  }, [state.sessionId, state.reveal])

  // ── Undo turn ────────────────────────────────────────────────────────────
  const undoTurn = useCallback(async () => {
    if (state.loading || !state.sessionId || state.questionNumber <= 1) return
    update({ loading: true, error: null })

    try {
      const data = await apiFetch(`/game/undo/${state.sessionId}`, { method: 'POST' })
      update(prev => ({
        ...prev,
        question: data.question,
        reasoning: data.reasoning,
        attribute: data.attribute,
        entropy: data.entropy,
        questionNumber: data.question_number,
        loading: false,
      }))
    } catch (err) {
      update({ error: err.message, loading: false })
    }
  }, [state.sessionId, state.loading, state.questionNumber])

  // ── Render ─────────────────────────────────────────────────────────────────
  const { phase, question, reasoning, questionNumber, top3, topConfidence,
          interpretedAnswer, loading, error, reveal } = state

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="header-logo">
          <span className="header-cricket">🏏</span>
          <div>
            <h2 className="header-title">IPL Akinator</h2>
            <p className="header-sub">Think of any IPL cricketer</p>
          </div>
        </div>
        <div className="header-right">
          <span className="badge badge-gold">Powered by Gemini</span>
          {phase === 'PLAYING' && (
            <button className="btn btn-ghost" style={{ padding: '8px 16px', fontSize: 13 }} onClick={startGame}>
              ↺ Restart
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        <AnimatePresence mode="wait">

          {/* ── IDLE screen ── */}
          {phase === 'IDLE' && (
            <motion.div
              key="idle"
              className="idle-screen"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -30 }}
            >
              <motion.div
                className="idle-icon"
                animate={{ y: [0, -16, 0], rotate: [0, 5, -5, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                🏏
              </motion.div>
              <h1 className="idle-title">Can I guess your IPL player?</h1>
              <p className="idle-desc">
                Think of any IPL cricketer. My AI will ask up to 12 smart questions
                and guess who you're thinking of — using Gemini + Bayesian reasoning.
              </p>
              <div className="idle-features">
                {[
                  ['🧠', 'Bayesian Reasoning', 'Probabilistic elimination, not guesswork'],
                  ['✨', 'Gemini Powered',      'Natural questions + dramatic reveal'],
                  ['📊', 'Live Confidence',    'Watch the AI narrow down candidates'],
                ].map(([icon, title, desc]) => (
                  <div key={title} className="feature-card glass-card">
                    <span className="feature-icon">{icon}</span>
                    <div>
                      <p className="feature-title">{title}</p>
                      <p className="feature-desc">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              {error && <p className="error-msg">⚠️ {error}</p>}
              <button
                className="btn btn-primary"
                onClick={startGame}
                disabled={loading}
                style={{ fontSize: 17, padding: '16px 48px', marginTop: 8 }}
              >
                {loading ? <><span className="spinner" /> Starting…</> : '🏏 Start Game'}
              </button>
            </motion.div>
          )}

          {/* ── PLAYING screen ── */}
          {phase === 'PLAYING' && (
            <motion.div
              key="playing"
              className="playing-layout"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Left — question */}
              <div className="playing-main">
                <QuestionCard
                  question={question}
                  reasoning={reasoning}
                  questionNumber={questionNumber}
                  maxQuestions={12}
                  interpretedAnswer={interpretedAnswer}
                  loading={loading}
                  onSubmit={submitAnswer}
                  onUndo={undoTurn}
                />
                {error && <p className="error-msg">⚠️ {error}</p>}
              </div>

              {/* Right — sidebar */}
              <aside className="playing-sidebar">
                <ConfidenceMeter
                  score={topConfidence}
                  topPlayer={top3[0]?.name ?? ''}
                  threshold={0.80}
                  reasoning={reasoning}
                  entropy={state.entropy}
                  isAiFallback={state.isAiFallback}
                />
                <ProbabilityBar candidates={top3} />
              </aside>
            </motion.div>
          )}

        </AnimatePresence>

        {/* ── REVEAL overlay ── */}
        <AnimatePresence>
          {phase === 'REVEALING' && reveal && (
            <RevealCard
              playerName={reveal.player_name}
              revealText={reveal.reveal_text}
              funFact={reveal.fun_fact}
              confidenceExplanation={reveal.confidence_explanation}
              finalConfidence={reveal.final_confidence}
              questionsAsked={reveal.questions_asked}
              onPlayAgain={() => { setState(INITIAL_STATE); startGame() }}
              onFeedback={() => setShowFeedback(true)}
            />
          )}
        </AnimatePresence>

        {/* ── FEEDBACK modal ── */}
        <AnimatePresence>
          {showFeedback && (
            <FeedbackModal
              sessionId={state.sessionId}
              guessedPlayer={reveal?.player_name ?? ''}
              onClose={() => setShowFeedback(false)}
              onSubmit={submitFeedback}
            />
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
