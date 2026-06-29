import { Slide } from '../Slide'
import type { SlideDef } from '../types'

/**
 * "One iteration becomes the prompt for the next one." — the agentic
 * experiment loop. Ported from docs/learn/playsim-agentic-simulator-deck.html.
 * The four stages are drawn as a live directed graph that cycles back up: a
 * glowing token travels planner → validator → workers → evaluator and loops
 * round to the planner, with the edges flowing in the same direction.
 */
const ARCH: { title: string; body: string }[] = [
  {
    title: 'Experiment spec',
    body: `{
  "policies": ["standard", "fairplay_liveness"],
  "sweep": {"tables": [4], "arrival_rate_per_hour": [60,72,84]},
  "max_sim_runs_per_experiment": 12
}`,
  },
  {
    title: 'Report finding',
    body: `FairPlay-liveness wins 1/3 cells.
Formation activates at high arrival pressure,
but vulnerable seat-hours decline.`,
  },
  {
    title: 'Next spec proposal',
    body: `Replicate the least-negative high-pressure cell
across more seeds before changing scoring.`,
  },
]

const NODES = ['LLM planner', 'Validator', 'Deterministic workers', 'Evaluator + report']
const ACCENT = '#5fcf8a'

// graph geometry (SVG user units) — large so node text reads on a projector
const NODE_W = 410
const NODE_H = 60
const NODE_CX = 350
const RAIL_X = 145 // left edge of every node; the return rail joins here
const YC = [36, 158, 280, 402] // node centre-y, top to bottom
// node 4 → out left → up the left rail → into node 1
const RETURN = 'C 80 415 44 380 44 340 L 44 98 C 44 58 80 24 145 36'
// the full loop the token rides: down the centre, across to the rail, up, back to start
const LOOP = `M ${NODE_CX} ${YC[0]} L ${NODE_CX} ${YC[3]} L ${RAIL_X} ${YC[3]} ${RETURN} L ${NODE_CX} ${YC[0]}`

function LoopGraph() {
  return (
    <svg
      viewBox="0 0 565 440"
      className="mx-auto block w-full max-w-[580px]"
      role="img"
      aria-label="Agentic loop: planner, validator, workers, evaluator, cycling back to the planner"
    >
      <defs>
        <marker
          id="ag-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill={ACCENT} />
        </marker>
        <filter id="ag-glow" x="-300%" y="-300%" width="700%" height="700%">
          <feGaussianBlur stdDeviation="3.5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* forward edges (down the centre), dashes marching toward the arrowhead */}
      {[0, 1, 2].map((i) => (
        <path
          key={i}
          d={`M ${NODE_CX} ${YC[i] + NODE_H / 2} L ${NODE_CX} ${YC[i + 1] - NODE_H / 2 - 2}`}
          fill="none"
          stroke="#3a5a48"
          strokeWidth={2.5}
          strokeDasharray="7 7"
          markerEnd="url(#ag-arrow)"
        >
          <animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.8s" repeatCount="indefinite" />
        </path>
      ))}

      {/* return edge — cycles back up to the planner */}
      <path
        d={`M ${RAIL_X} ${YC[3]} ${RETURN}`}
        fill="none"
        stroke="#3a5a48"
        strokeWidth={2.5}
        strokeDasharray="7 7"
        markerEnd="url(#ag-arrow)"
      >
        <animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.8s" repeatCount="indefinite" />
      </path>
      <text
        x="34"
        y="226"
        transform="rotate(-90 34 226)"
        textAnchor="middle"
        fontSize="13"
        fill="#7c8698"
        letterSpacing="2"
      >
        loops back
      </text>

      {/* nodes */}
      {NODES.map((label, i) => {
        const x = NODE_CX - NODE_W / 2
        const y = YC[i] - NODE_H / 2
        return (
          <g key={label}>
            <rect
              x={x}
              y={y}
              width={NODE_W}
              height={NODE_H}
              rx={14}
              fill="#11161f"
              stroke="rgba(95,207,138,0.55)"
              strokeWidth={1.75}
            />
            <circle cx={x + 36} cy={YC[i]} r={19} fill="#2f8f5b" />
            <text x={x + 36} y={YC[i] + 7} textAnchor="middle" fontSize="22" fontWeight="700" fill="#eafff3">
              {i + 1}
            </text>
            <text x={x + 74} y={YC[i] + 9} fontSize="28" fontWeight="600" fill="#eaf1fb">
              {label}
            </text>
          </g>
        )
      })}

      {/* the live token riding the loop */}
      <circle r="8" fill="#eafff3" filter="url(#ag-glow)">
        <animateMotion dur="5.5s" repeatCount="indefinite" path={LOOP} />
      </circle>
    </svg>
  )
}

function AgenticSlide() {
  return (
    <Slide kicker="Agentic loop architecture" title="One iteration becomes the prompt for the next one.">
      <div className="grid gap-6" style={{ gridTemplateColumns: 'minmax(0,0.82fr) minmax(0,1.18fr)' }}>
        {/* left: the artifacts that flow around the loop */}
        <div className="flex flex-col gap-3">
          {ARCH.map((a) => (
            <div key={a.title} className="rounded-xl border border-line bg-surface p-4">
              <div className="font-mono text-[1.08rem] uppercase tracking-[0.16em] text-brass">
                {a.title}
              </div>
              <pre className="m-0 mt-2 whitespace-pre-wrap font-mono text-[0.78rem] leading-snug text-[#c8d0de]">
                {a.body}
              </pre>
            </div>
          ))}
        </div>

        {/* right: the live agentic loop */}
        <div className="flex items-center justify-center">
          <LoopGraph />
        </div>
      </div>
    </Slide>
  )
}

/** In-slide staged-reveal control: an action button + progress dots. Shared kit
 * piece — used by the routing slide. */
export function StageControl({
  label,
  stage,
  total,
  onAdvance,
}: {
  label: string
  stage: number
  total: number
  onAdvance: () => void
}) {
  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        onClick={onAdvance}
        className="rounded-full border border-brass bg-[rgba(199,154,75,0.12)] px-5 py-2 text-[0.95rem] font-semibold text-brass transition-colors hover:bg-[rgba(199,154,75,0.22)]"
      >
        {label} →
      </button>
      <div className="flex gap-1.5" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className="h-[0.45rem] w-[0.45rem] rounded-full transition-colors"
            style={{ background: i <= stage ? '#c79a4b' : '#3a4757' }}
          />
        ))}
      </div>
    </div>
  )
}

export const agenticSlide: SlideDef = {
  id: 'agentic-loop',
  label: 'Agentic loop',
  Component: AgenticSlide,
}
