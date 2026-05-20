import { motion } from 'framer-motion'
import './ProbabilityBar.css'

const RANK_COLORS = {
  1: { fill: 'rank-1', text: 'var(--accent-gold)' },
  2: { fill: 'rank-2', text: 'var(--accent-blue)' },
  3: { fill: 'rank-3', text: 'var(--accent-purple)' },
}

const RANK_LABELS = { 1: '🥇', 2: '🥈', 3: '🥉' }

export default function ProbabilityBar({ candidates = [] }) {
  if (!candidates.length) {
    return (
      <div className="glass-card prob-bar-container">
        <div className="prob-bar-title">Top Candidates</div>
        <div className="no-candidates">Waiting for first answer…</div>
      </div>
    )
  }

  return (
    <div className="glass-card prob-bar-container">
      <div className="prob-bar-title">Top Candidates</div>

      {candidates.map((c, i) => {
        const rank = i + 1
        const displayPct = (c.score * 100).toFixed(1)
        const { fill, text } = RANK_COLORS[rank] || RANK_COLORS[3]

        return (
          <motion.div
            key={c.player_id || c.name}
            className="candidate-row"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <div className="candidate-meta">
              <div className="flex items-center gap-2">
                <span className="candidate-rank">{RANK_LABELS[rank]}</span>
                <span className="candidate-name">{c.name}</span>
              </div>
              <span className="candidate-score" style={{ color: text }}>{displayPct}%</span>
            </div>
            <div className="bar-track">
              <motion.div
                className={`bar-fill ${fill}`}
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(2, parseFloat(displayPct))}%` }}
                transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
              />
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
