import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function FeedbackModal({ sessionId, guessedPlayer, onClose, onSubmit }) {
  const [correctPlayer, setCorrectPlayer] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!correctPlayer.trim()) return
    setLoading(true)
    try {
      await onSubmit(correctPlayer.trim())
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        style={{
          position: 'fixed', inset: 0, background: 'rgba(6,6,18,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 200, padding: 20,
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="glass-card"
          style={{ maxWidth: 400, width: '100%', padding: 32, display: 'flex', flexDirection: 'column', gap: 20 }}
          initial={{ scale: 0.85, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          onClick={e => e.stopPropagation()}
        >
          {submitted ? (
            <motion.div
              style={{ textAlign: 'center', padding: '12px 0' }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <div style={{ fontSize: 40, marginBottom: 12 }}>🙏</div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 8 }}>Thank you!</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                We'll use your feedback to improve future games.
              </p>
              <button className="btn btn-primary" style={{ marginTop: 20, width: '100%' }} onClick={onClose}>
                Close
              </button>
            </motion.div>
          ) : (
            <>
              <div>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 6 }}>
                  Wrong guess?
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.5 }}>
                  We guessed <strong style={{ color: 'var(--accent-gold)' }}>{guessedPlayer}</strong>.
                  Who were you actually thinking of?
                </p>
              </div>

              <input
                className="input"
                value={correctPlayer}
                onChange={e => setCorrectPlayer(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                placeholder="Enter the correct player name…"
                autoFocus
              />

              <div style={{ display: 'flex', gap: 10 }}>
                <button className="btn btn-ghost" onClick={onClose} style={{ flex: 1 }}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleSubmit}
                  disabled={!correctPlayer.trim() || loading}
                  style={{ flex: 1 }}
                >
                  {loading ? <span className="spinner" /> : 'Submit'}
                </button>
              </div>
            </>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
