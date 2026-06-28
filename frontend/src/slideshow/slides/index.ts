import type { SlideDef } from '../types'
import { titleSlide } from './title'
import { industrySlide } from './industry'
import { economicsSlide } from './economics'
import { questionSlide } from './question'
import { approachSlide } from './approach'
import { lobbySlide } from './lobby'
import { tableSlide } from './table'
import { intelligenceSlide } from './intelligence'
import { dashboardSlide } from './dashboard'
import { closeSlide } from './close'

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
  approachSlide, // 5 · FairPlay routing
  lobbySlide, // 6 · player lobby (placeholder)
  tableSlide, // 7 · zoom into a table (placeholder)
  intelligenceSlide, // 8 · the intelligence behind it
  dashboardSlide, // 9 · the 8-hour A/B results
  closeSlide, // 10 · close
]
