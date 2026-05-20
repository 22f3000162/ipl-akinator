import { motion } from 'framer-motion'
import { useState } from 'react'
import './RevealCard.css'

export default function RevealCard({
  playerName,
  revealText,
  funFact,
  confidenceExplanation,
  finalConfidence,
  questionsAsked,
  onPlayAgain,
  onFeedback,
  wasCorrect,
}) {
  const pct = Math.round(finalConfidence * 100)

  return (
    <motion.div
      className="reveal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Confetti burst rings */}
      {[...Array(3)].map((_, i) => (
        <motion.div
          key={i}
          className="burst-ring"
          initial={{ scale: 0, opacity: 0.8 }}
          animate={{ scale: 3 + i, opacity: 0 }}
          transition={{ duration: 1.2 + i * 0.3, delay: i * 0.15, ease: 'easeOut' }}
        />
      ))}

      <motion.div
        className="reveal-card glass-card"
        initial={{ scale: 0.7, opacity: 0, rotateX: -20 }}
        animate={{ scale: 1, opacity: 1, rotateX: 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20, delay: 0.1 }}
      >
        {/* Trophy */}
        <motion.div
          className="reveal-trophy"
          animate={{ y: [0, -12, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        >
          🏆
        </motion.div>

        {/* Player name */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <p className="reveal-label">The mystery cricketer is…</p>
          <h1 className="reveal-name">{playerName}</h1>
        </motion.div>

        {/* Stats row */}
        <motion.div
          className="reveal-stats"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
        >
          <div className="stat-pill">
            <span className="stat-value">{pct}%</span>
            <span className="stat-label">confidence</span>
          </div>
          <div className="stat-pill">
            <span className="stat-value">{questionsAsked}</span>
            <span className="stat-label">questions</span>
          </div>
        </motion.div>

        {/* Reveal text */}
        <motion.p
          className="reveal-text"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.55 }}
        >
          {revealText}
        </motion.p>

        <div className="divider" />

        {/* Fun fact */}
        <motion.div
          className="fun-fact-box"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.65 }}
        >
          <span className="fun-fact-icon">💡</span>
          <div>
            <p className="fun-fact-label">Fun Fact</p>
            <p className="fun-fact-text">{funFact}</p>
          </div>
        </motion.div>

        {/* AI reasoning (judge-facing) */}
        {confidenceExplanation && (
          <motion.div
            className="reasoning-reveal-box"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.75 }}
          >
            <span>🧠</span>
            <p>{confidenceExplanation}</p>
          </motion.div>
        )}

        {/* Action buttons */}
        <motion.div
          className="reveal-actions"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.85 }}
        >
          <button className="btn btn-primary" onClick={onPlayAgain} style={{ flex: 1 }}>
            🏏 Play Again
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => onFeedback(false)}
            style={{ flex: 1 }}
          >
            ✗ Wrong? Tell us
          </button>
        </motion.div>
      </motion.div>
    </motion.div>
  )
}
