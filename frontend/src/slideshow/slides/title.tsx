import logo from '../../assets/fairplay-iq-logo-brass.svg'
import { Slide } from '../Slide'
import type { SlideDef } from '../types'

function TitleSlide() {
  return (
    <Slide center>
      <div className="flex flex-col items-start gap-6">
        <img className="h-[64px] w-auto" src={logo} alt="FairPlay IQ" />
        <h1 className="m-0 text-[3.4rem] font-bold leading-[1.05] tracking-[-0.01em] text-text">
          Healthier tables,
          <br />
          longer play.
        </h1>
        <p className="m-0 max-w-[46ch] text-[1.4rem] leading-snug text-muted">
          An AI simulation lab and operator copilot for online-poker table health and integrity.
        </p>
        <p className="m-0 flex items-center gap-[0.55rem] font-mono text-[0.72rem] uppercase tracking-[0.22em] text-faint">
          <span className="h-2 w-2 rounded-full bg-felt shadow-[0_0_0_3px_rgba(47,143,91,0.18)]" />
          Synthetic data · recommend, explain, human decides
        </p>
      </div>
    </Slide>
  )
}

export const titleSlide: SlideDef = {
  id: 'title',
  label: 'FairPlay IQ',
  Component: TitleSlide,
}
