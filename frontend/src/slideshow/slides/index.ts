import type { SlideDef } from '../types'
import { titleSlide } from './title'
import { industrySlide } from './industry'
import { moneySlide } from './problemMoney'
import { seatTimeSlide } from './problemSeatTime'
import { rankHealthSlide } from './approachRankHealth'
import { lobbyStandardSlide } from './lobbyStandard'
import { approachSlide } from './approach'
import { lobbySlide } from './lobby'
import { tableSlide } from './table'
import { routingSlide } from './routing'
import { evidenceSlide } from './evidence'
import { agenticSlide } from './agentic'

/**
 * The deck, in order. This array IS the presentation — reorder, add, or remove
 * entries here. To add a slide: create a file in this folder, export a SlideDef,
 * import it above, and slot it into the array. See ../README.md.
 *
 * Pared down per Jordan's script — other slide files still live in this folder
 * (problemDecay, approachScore, approachGuardrails, economics, question,
 * approach, standardRouting, intelligence, dashboard, close); re-import any to
 * bring it back.
 */
export const SLIDES: SlideDef[] = [
  titleSlide, // 1 · intro — FairPlay IQ, increase play time via table health
  industrySlide, // 2 · the market — $6B, growing double digits
  moneySlide, // 3 · two ways to make money — rake vs seat rental
  seatTimeSlide, // 4 · duration is king — time seated, not money changing hands
  rankHealthSlide, // 5 · our thesis — rank by health, route to the healthiest
  lobbyStandardSlide, // 6 · industry standard today — fullest tables first
  approachSlide, // 7 · our approach — route players toward healthier tables
  lobbySlide, // 8 · player lobby (live, Standard vs FairPlay)
  tableSlide, // 9 · zoom into a table (live curtain)
  routingSlide, // 10 · policy routing behavior (staged + animated)
  evidenceSlide, // 11 · why we simulate — the knobs
  agenticSlide, // 12 · the agentic experiment loop (staged)
]
