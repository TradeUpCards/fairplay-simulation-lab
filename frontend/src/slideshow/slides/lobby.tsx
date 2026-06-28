import { Slide, Placeholder } from '../Slide'
import type { SlideDef } from '../types'

function LobbySlide() {
  return (
    <Slide kicker="1 · Player floor" title="The lobby — neutral and player-safe">
      <div className="flex h-full flex-col gap-5">
        <p className="m-0 max-w-[64ch] text-[1.15rem] leading-relaxed text-muted">
          Players see stakes, open seats, pace, and a simple{' '}
          <span className="text-brass">&ldquo;Recommended for you&rdquo;</span> — never health
          scores, player classifications, or risk language. That wall is enforced in the types.
        </p>
        {/* COLLEAGUE: drop the live lobby view (or a screenshot) in place of this
            placeholder. The component lives at src/views/PlayerLobby.tsx; an
            updated version is pending a push. */}
        <Placeholder title="Lobby view">
          Pending a teammate&apos;s push. Swap this for the live <code>PlayerLobby</code> or a
          screenshot — see the comment in this slide file.
        </Placeholder>
      </div>
    </Slide>
  )
}

export const lobbySlide: SlideDef = {
  id: 'lobby',
  label: 'Player lobby',
  Component: LobbySlide,
}
