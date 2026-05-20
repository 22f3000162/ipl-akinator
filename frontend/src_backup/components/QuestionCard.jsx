import { motion, AnimatePresence } from 'framer-motion'
import { useState, useRef, useEffect } from 'react'
import './QuestionCard.css'

const ANSWER_TAGS = {
  YES:       { label: 'Yes',       color: 'var(--accent-green)',  bg: 'rgba(52,211,153,0.12)',  icon: '✓' },
  NO:        { label: 'No',        color: 'var(--accent-red)',    bg: 'rgba(248,113,113,0.12)', icon: '✗' },
  MAYBE:     { label: 'Maybe',     color: 'var(--accent-gold)',   bg: 'rgba(245,166,35,0.12)',  icon: '~' },
  DONT_KNOW: { label: "Don't know",color: 'var(--text-muted)',    bg: 'rgba(255,255,255,0.05)', icon: '?' },
}

const QUICK_ANSWERS = [
  { label: '✓  Yes',      value: 'yes',         cls: 'yes'  },
  { label: '✗  No',       value: 'no',          cls: 'no'   },
  { label: '~  Maybe',    value: 'maybe',       cls: 'maybe'},
  { label: "?  Don't know", value: "don't know", cls: 'dk'  },
]

const QUESTION_EMOJIS = ['🏏', '🎯', '🤔', '🧠', '💡', '🔍', '⚡', '🏆']

export default function QuestionCard({
  question,
  reasoning,
  questionNumber,
  maxQuestions = 12,
  interpretedAnswer,
  loading,
  onSubmit,
  onUndo,
}) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)
  const emoji = QUESTION_EMOJIS[(questionNumber - 1) % QUESTION_EMOJIS.length]

  useEffect(() => {
    setText('')
    inputRef.current?.focus()
  }, [question])

  const handleSubmit = (value) => {
    const ans = value ?? text.trim()
    if (!ans || loading) return
    onSubmit(ans)
  }

  const tag = interpretedAnswer ? ANSWER_TAGS[interpretedAnswer] : null

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={question}
        className="glass-card question-card"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -24 }}
        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
      >
        {/* Header */}
        <div className="question-header">
          <div className="flex items-center gap-2">
            {questionNumber > 1 && (
              <button 
                className="back-btn" 
                onClick={onUndo} 
                disabled={loading}
                title="Go back to previous question"
              >
                ←
              </button>
            )}
            <span className="question-number-pill">
              🏏 Question {questionNumber} of {maxQuestions}
            </span>
          </div>
          {tag && (
            <motion.span
              className="interpreted-tag"
              style={{ color: tag.color, background: tag.bg, border: `1px solid ${tag.color}33` }}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              {tag.icon} {tag.label}
            </motion.span>
          )}
        </div>

        {/* Question */}
        <div className="flex items-center gap-3">
          <span className="question-emoji">{loading ? '🧠' : emoji}</span>
          {loading ? (
            <div className="loading-question">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <span className="loading-text">Gemini is analyzing candidates…</span>
            </div>
          ) : (
            <p className="question-text">{question}</p>
          )}
        </div>

        {/* Answer area */}
        <div className="answer-area">
          {/* Quick-answer chips */}
          <div className="quick-answers">
            {QUICK_ANSWERS.map(q => (
              <button
                key={q.value}
                className={`quick-btn ${q.cls}`}
                onClick={() => handleSubmit(q.value)}
                disabled={loading}
              >
                {q.label}
              </button>
            ))}
          </div>

          {/* Free-text input */}
          <div className="input-row">
            <input
              ref={inputRef}
              className="input"
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="Or type your answer…"
              disabled={loading}
            />
            <button
              className="btn btn-primary"
              onClick={() => handleSubmit()}
              disabled={loading || !text.trim()}
              style={{ whiteSpace: 'nowrap', minWidth: 90 }}
            >
              {loading ? <span className="spinner" /> : 'Answer →'}
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
