import t05Lobby from '../../assets/t05-lobby.png'
import { Slide } from '../Slide'
import type { SlideDef } from '../types'

function LobbySlide() {
  return (
    <Slide kicker="Player floor" title="Same table, opposite verdict">
      <div className="flex h-full flex-col gap-4">
        <p className="m-0 max-w-[80ch] text-[1.12rem] leading-relaxed text-muted">
          One room, seated by two policies. Watch table{' '}
          <span className="font-semibold text-text">T-05</span>:{' '}
          <span className="font-semibold text-brass">Standard</span> ranks it{' '}
          <span className="text-text">#3</span> — it&apos;s full, so &ldquo;join it.&rdquo;{' '}
          <span className="font-semibold text-[#5fcf8a]">FairPlay</span> buries it{' '}
          <span className="text-text">dead last among open tables</span>. To a player it just looks
          busy — the split only shows once you pull back the curtain.
        </p>
        <div className="grid min-h-0 flex-1 place-items-center overflow-hidden rounded-xl border border-line bg-[#0b0e13] shadow-[0_10px_24px_rgba(0,0,0,0.42)]">
          <img
            src={t05Lobby}
            alt="Standard vs FairPlay lobby — table T-05 ranked #3 in Standard, last among open tables in FairPlay"
            className="max-h-full max-w-full object-contain"
          />
        </div>
      </div>
    </Slide>
  )
}

export const lobbySlide: SlideDef = {
  id: 'lobby',
  label: 'Player lobby',
  Component: LobbySlide,
}
