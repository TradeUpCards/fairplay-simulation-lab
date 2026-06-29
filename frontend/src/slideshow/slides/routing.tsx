import { useState } from 'react'
import type { CSSProperties } from 'react'
import { Slide } from '../Slide'
import { StageControl } from './agentic'
import { useStageKeys } from '../useStageKeys'
import type { SlideDef } from '../types'

/**
 * "Same arrivals, different table-filling strategy." — the policy routing
 * behaviour. Ported from docs/learn/playsim-agentic-simulator-deck.html: three
 * policy rows revealed in stages (Standard → FairPlay → FairPlay-liveness),
 * each with arrivals flowing into mini-tables whose seats fill in a different
 * order. Re-skinned from the source deck's light/teal look to this deck's
 * ink + brass + felt theme; the animation + staged reveal are preserved, with
 * the slide owning its own stage state.
 */
const cssVars = (o: Record<string, string | number>) => o as CSSProperties

// scoped under `.pr8` so the animation styles never leak into the rest of the app
const CSS = `
.pr8 .pf { display:grid; gap:12px; }
.pr8 .pf-row {
  display:grid; grid-template-columns: 196px minmax(0,1fr); gap:14px; align-items:stretch;
  min-height:0; max-height:0; overflow:hidden; opacity:0; transform:translateY(12px);
  pointer-events:none; transition:opacity 360ms ease, transform 360ms ease, max-height 360ms ease;
}
.pr8[data-stage="0"] .pf-row[data-step="0"],
.pr8[data-stage="1"] .pf-row[data-step="0"],
.pr8[data-stage="1"] .pf-row[data-step="1"],
.pr8[data-stage="2"] .pf-row {
  min-height:138px; max-height:200px; opacity:1; transform:translateY(0); pointer-events:auto;
}
.pr8 .pcard {
  border:1px solid #232a36; border-radius:12px; padding:15px; background:#161b24;
  display:grid; align-content:center; gap:7px;
}
.pr8 .pf-row[data-step="0"] .pcard { border-left:5px solid #53627a; }
.pr8 .pf-row[data-step="1"] .pcard { border-left:5px solid #c79a4b; }
.pr8 .pf-row[data-step="2"] .pcard { border-left:5px solid #5fcf8a; }
.pr8 .pcard b { font-size:1.15rem; line-height:1.1; color:#e6e9ef; }
.pr8 .pcard span { color:#aeb6c4; font-size:1.03rem; line-height:1.38; }

.pr8 .stage {
  position:relative; min-height:138px; border:1px solid #232a36; border-radius:12px;
  padding:14px 16px; overflow:hidden;
  background:
    linear-gradient(90deg, rgba(17,22,31,0.96), rgba(22,27,36,0.96)),
    repeating-linear-gradient(90deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 46px);
}
.pr8 .arrivals { position:absolute; left:16px; top:12px; color:#7c8698; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; }
.pr8 .tables { position:absolute; inset:34px 14px 12px 124px; display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px; z-index:2; }
.pr8 .mt { position:relative; border:1px solid #2c3543; border-radius:11px; padding:9px; background:rgba(255,255,255,0.02); display:grid; align-content:space-between; min-width:0; }
.pr8 .mt.full { background:rgba(255,255,255,0.05); }
.pr8 .mt.empty { background:rgba(255,255,255,0.012); }
.pr8 .mt-title { display:flex; justify-content:space-between; gap:8px; font-size:11px; font-weight:800; color:#dbe1ea; }
.pr8 .mt-title small { color:#7c8698; font-weight:700; }
.pr8 .seats { display:grid; grid-template-columns:repeat(3, 16px); gap:6px; justify-content:center; padding-top:6px; }
.pr8 .seat { width:16px; height:16px; border-radius:50%; border:1px solid #3a4757; background:transparent; }
.pr8 .seat.filled { background:#6b7283; border-color:#6b7283; }
.pr8 .seat.vulnerable { background:#e0697f; border-color:#e0697f; }
.pr8 .seat.fit { background:#c79a4b; border-color:#c79a4b; }
.pr8 .seat.rf { animation:pr8Fill 12s ease-in-out infinite; animation-delay:var(--fill-delay,0s); }
.pr8 .seat.rf.t3 { animation-name:pr8Fill3; }
.pr8 .seat.rf.gold { --fill-color:#c79a4b; --fill-border:#c79a4b; }
.pr8 .seat.rf.coral { --fill-color:#e0697f; --fill-border:#e0697f; }
.pr8 .runner {
  position:absolute; left:18px; top:var(--y); width:14px; height:14px; border-radius:50%;
  background:#5fcf8a; border:2px solid rgba(255,255,255,0.85); box-shadow:0 3px 10px rgba(47,143,91,0.45);
  z-index:3; animation:pr8Flow var(--speed,8.16s) linear infinite; animation-delay:var(--delay,0s);
}
.pr8 .runner.gold { background:#c79a4b; box-shadow:0 3px 10px rgba(199,154,75,0.4); }
.pr8 .runner.coral { background:#e0697f; box-shadow:0 3px 10px rgba(224,105,127,0.4); }
@keyframes pr8Flow {
  0% { transform:translate(0,0) scale(0.75); opacity:0; }
  10% { opacity:1; }
  78% { transform:translate(var(--x), var(--dy,0px)) scale(1); opacity:1; }
  100% { transform:translate(var(--x), var(--dy,0px)) scale(0.8); opacity:0; }
}
@keyframes pr8Fill {
  0%,10% { background:transparent; border-color:#3a4757; box-shadow:none; transform:scale(1); }
  16%,82% { background:var(--fill-color,#5fcf8a); border-color:var(--fill-border,#5fcf8a); box-shadow:0 0 0 4px rgba(95,207,138,0.16); transform:scale(1.1); }
  92%,100% { background:transparent; border-color:#3a4757; box-shadow:none; transform:scale(1); }
}
@keyframes pr8Fill3 {
  0%,46% { background:transparent; border-color:#3a4757; box-shadow:none; transform:scale(1); }
  52%,82% { background:var(--fill-color,#5fcf8a); border-color:var(--fill-border,#5fcf8a); box-shadow:0 0 0 4px rgba(95,207,138,0.16); transform:scale(1.1); }
  92%,100% { background:transparent; border-color:#3a4757; box-shadow:none; transform:scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .pr8 .runner { display:none; }
  .pr8 .seat.rf { animation:none; }
}
`

/** Table 1 is the same "already full" reference table in every row. */
function FullTable() {
  return (
    <div className="mt full">
      <div className="mt-title">
        <span>Table 1</span>
        <small>6/6</small>
      </div>
      <div className="seats" aria-hidden="true">
        <span className="seat filled" />
        <span className="seat vulnerable" />
        <span className="seat filled" />
        <span className="seat filled" />
        <span className="seat fit" />
        <span className="seat filled" />
      </div>
    </div>
  )
}

function RoutingSlide() {
  const [stage, setStage] = useState(0)
  const advance = () => setStage((s) => (s >= 2 ? 0 : s + 1))
  const STAGE_LABELS = ['Show FairPlay', 'Show Liveness', 'Replay']
  // → / ← step through the policy rows before the deck moves on
  useStageKeys(stage, 3, setStage)

  return (
    <Slide kicker="Policy routing behavior" title="Same arrivals, different table-filling strategy.">
      <div className="flex flex-col gap-6">
        <div className="pr8" data-stage={stage}>
          <style>{CSS}</style>
          <div className="pf">
            {/* Standard */}
            <section className="pf-row" data-step="0">
              <div className="pcard">
                <b>Standard</b>
                <span>Top off the next available table.</span>
              </div>
              <div className="stage">
                <span className="arrivals">Arrivals</span>
                <span className="runner" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '46px', '--dy': '2px', '--delay': '0.4s' })} />
                <span className="runner gold" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '72px', '--dy': '-4px', '--delay': '2s' })} />
                <span className="runner" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '98px', '--dy': '-8px', '--delay': '3.6s' })} />
                <span className="runner coral" style={cssVars({ '--x': 'min(62vw,600px)', '--y': '110px', '--dy': '-14px', '--delay': '8.2s' })} />
                <div className="tables">
                  <FullTable />
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 2</span>
                      <small>starts 0/6, fills first</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat rf" style={cssVars({ '--fill-delay': '.6s' })} />
                      <span className="seat rf gold" style={cssVars({ '--fill-delay': '1.7s' })} />
                      <span className="seat rf" style={cssVars({ '--fill-delay': '2.8s' })} />
                      <span className="seat rf coral" style={cssVars({ '--fill-delay': '3.9s' })} />
                      <span className="seat rf" style={cssVars({ '--fill-delay': '5s' })} />
                      <span className="seat rf gold" style={cssVars({ '--fill-delay': '6.1s' })} />
                    </div>
                  </div>
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 3</span>
                      <small>late overflow</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat rf t3 coral" style={cssVars({ '--fill-delay': '8.1s' })} />
                      <span className="seat" /><span className="seat" />
                      <span className="seat" /><span className="seat" /><span className="seat" />
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* FairPlay */}
            <section className="pf-row" data-step="1">
              <div className="pcard">
                <b>FairPlay</b>
                <span>Ranks by health and fit. Empty tables split demand.</span>
              </div>
              <div className="stage">
                <span className="arrivals">Arrivals</span>
                <span className="runner gold" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '48px', '--dy': '0px', '--delay': '.6s' })} />
                <span className="runner" style={cssVars({ '--x': 'min(62vw,600px)', '--y': '78px', '--dy': '-8px', '--delay': '2.2s' })} />
                <span className="runner coral" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '108px', '--dy': '-14px', '--delay': '3.8s' })} />
                <span className="runner" style={cssVars({ '--x': 'min(62vw,600px)', '--y': '52px', '--dy': '8px', '--delay': '5.4s' })} />
                <div className="tables">
                  <FullTable />
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 2</span>
                      <small>arrival 1, 3</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat rf gold" style={cssVars({ '--fill-delay': '.8s' })} />
                      <span className="seat" />
                      <span className="seat rf coral" style={cssVars({ '--fill-delay': '3.8s' })} />
                      <span className="seat" /><span className="seat" /><span className="seat" />
                    </div>
                  </div>
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 3</span>
                      <small>arrival 2, 4</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat" />
                      <span className="seat rf t3" style={cssVars({ '--fill-delay': '2.3s' })} />
                      <span className="seat" />
                      <span className="seat rf t3" style={cssVars({ '--fill-delay': '5.4s' })} />
                      <span className="seat" /><span className="seat" />
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* FairPlay-liveness */}
            <section className="pf-row" data-step="2">
              <div className="pcard">
                <b>FairPlay-liveness</b>
                <span>
                  Uses health and liveness: concentrate compatible arrivals before seeding another
                  empty table.
                </span>
              </div>
              <div className="stage">
                <span className="arrivals">Arrivals</span>
                <span className="runner" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '46px', '--dy': '4px', '--delay': '.6s' })} />
                <span className="runner gold" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '78px', '--dy': '-3px', '--delay': '2.1s' })} />
                <span className="runner coral" style={cssVars({ '--x': 'min(46vw,440px)', '--y': '108px', '--dy': '-9px', '--delay': '3.6s' })} />
                <span className="runner" style={cssVars({ '--x': 'min(62vw,600px)', '--y': '58px', '--dy': '8px', '--delay': '6.1s' })} />
                <div className="tables">
                  <FullTable />
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 2</span>
                      <small>0/6 → 3-seat quorum</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat rf" style={cssVars({ '--fill-delay': '.7s' })} />
                      <span className="seat rf gold" style={cssVars({ '--fill-delay': '2.1s' })} />
                      <span className="seat rf coral" style={cssVars({ '--fill-delay': '3.6s' })} />
                      <span className="seat" /><span className="seat" /><span className="seat" />
                    </div>
                  </div>
                  <div className="mt empty">
                    <div className="mt-title">
                      <span>Table 3</span>
                      <small>after quorum</small>
                    </div>
                    <div className="seats" aria-hidden="true">
                      <span className="seat rf t3" style={cssVars({ '--fill-delay': '6.1s' })} />
                      <span className="seat" /><span className="seat" />
                      <span className="seat" /><span className="seat" /><span className="seat" />
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>

        <StageControl label={STAGE_LABELS[stage]} stage={stage} total={3} onAdvance={advance} />
      </div>
    </Slide>
  )
}

export const routingSlide: SlideDef = {
  id: 'policy-routing',
  label: 'Routing behavior',
  Component: RoutingSlide,
}
