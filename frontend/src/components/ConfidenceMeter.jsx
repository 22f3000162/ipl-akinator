import { motion } from 'framer-motion'
import './ConfidenceMeter.css'

const SIZE = 140
const STROKE = 10
const R = (SIZE - STROKE) / 2
const CIRC = 2 * Math.PI * R
// Arc spans 270° (from 135° to 45°)
const ARC = CIRC * 0.75

function getColor(pct) {
  if (pct >= 80) return 'var(--accent-green)'
  if (pct >= 50) return 'var(--accent-gold)'
  return 'var(--accent-blue)'
}

export default function ConfidenceMeter({ 
  score = 0, 
  topPlayer = '', 
  threshold = 0.80,
  reasoning = '',
  entropy = null,
  isAiFallback = false
}) {
  const pct = Math.round(score * 100)
  const filled = ARC * (pct / 100)
  const offset = ARC - filled
  const color = getColor(pct)
  const isHigh = pct >= threshold * 100

  return (
    <div className="confidence-stack">
      <div className="glass-card confidence-meter">
        <div className="meter-title">AI Confidence</div>

        <div style={{ position: 'relative', width: SIZE, height: SIZE * 0.85 }}>
          <svg
            className="arc-svg"
            width={SIZE}
            height={SIZE * 0.85}
            style={{ display: 'block' }}
          >
            {/* Background arc */}
            <circle
              className="arc-bg"
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={R}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={`${ARC} ${CIRC - ARC}`}
              strokeDashoffset={-CIRC * 0.125}
              transform={`rotate(90 ${SIZE / 2} ${SIZE / 2})`}
            />
            {/* Filled arc */}
            <motion.circle
              className="arc-fill"
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={R}
              fill="none"
              stroke={color}
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={`${ARC} ${CIRC - ARC}`}
              strokeDashoffset={offset}
              transform={`rotate(90 ${SIZE / 2} ${SIZE / 2})`}
              style={{ color }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
            />
          </svg>

          {/* Center content */}
          <div
            className="meter-center"
            style={{
              position: 'absolute',
              top: '40%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          >
            <motion.span
              className="meter-pct"
              style={{ color }}
              animate={{ color }}
              key={pct}
            >
              {pct < 10 ? (score * 100).toFixed(1) : pct}%
            </motion.span>
            <span className="meter-label">confidence</span>
          </div>
        </div>

        {topPlayer && (
          <motion.div
            className="meter-player"
            key={topPlayer}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ color: isHigh ? color : 'var(--text-secondary)' }}
          >
            {isHigh ? '🎯 ' : ''}{topPlayer}
          </motion.div>
        )}

        <div className="threshold-line">
          <span className="threshold-dot" />
          <span>Guess threshold: {Math.round(threshold * 100)}%</span>
        </div>

        {isAiFallback && (
          <div className="ai-status-badge fallback">
            <span className="status-icon">⚠️</span>
            <span>AI Status: Rate-Limited (Keyword Mode)</span>
          </div>
        )}
      </div>

      {/* Judge Explainability Sidebar */}
      {reasoning && (
        <motion.div 
          className="glass-card explain-box"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          key={reasoning}
        >
          <div className="explain-header">
            <span className="explain-icon">🧠</span>
            <span className="explain-title">AI Reasoning</span>
            {entropy !== null && (
              <span className="entropy-badge">
                Gain: {entropy.toFixed(2)} bits
              </span>
            )}
          </div>
          <p className="explain-text">{reasoning}</p>
          <div className="explain-footer">
            <span className="pulse-dot" />
            Live decision engine
          </div>
        </motion.div>
      )}
    </div>
  )
}
