import type { SlideDef } from '../types'
import { titleSlide } from './title'
import { industrySlide } from './industry'
import { economicsSlide } from './economics'
import { questionSlide } from './question'
import { approachSlide } from './approach'
import { lobbyStandardSlide } from './lobbyStandard'
import { lobbySlide } from './lobby'
import { tableSlide } from './table'
import { routingSlide } from './routing'
import { evidenceSlide } from './evidence'
import { agenticSlide } from './agentic'

/**
 * The deck, in order. This array IS the presentation — reorder, add, or remove
 * entries here. To add a slide: create a file in this folder, export a SlideDef,
 * import it above, and slot it into the array. See ../README.md.
 */
export const SLIDES: SlideDef[] = [
  titleSlide, // 1 · title
  industrySlide, // 2 · the market
  economicsSlide, // 3 · rake vs seat rental
  questionSlide, // 4 · how do we increase play time?
  lobbyStandardSlide, // 5 · the lobby today (Standard only, locked)
  approachSlide, // 6 · FairPlay routing
  lobbySlide, // 7 · player lobby (live, Standard vs FairPlay)
  tableSlide, // 8 · zoom into a table (live curtain)
  // — appended: the agentic experiment-engine deck (ported from
  //   docs/learn/playsim-agentic-simulator-deck.html) —
  routingSlide, // 9 · policy routing behavior (staged + animated)
  evidenceSlide, // 10 · why we simulate — the knobs
  agenticSlide, // 11 · the agentic experiment loop (staged)
]
