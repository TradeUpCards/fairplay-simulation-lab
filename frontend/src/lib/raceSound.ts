/**
 * Tiny WebAudio synth for the replay "race" — no asset files, ported from
 * demo/fairplay-live-sim.html. A module singleton. Every method is a safe no-op
 * until the AudioContext is created on a user gesture (`resume()`), while muted,
 * or when WebAudio is unavailable (e.g. jsdom under tests) — so callers never
 * need to guard.
 */
type MaybeCtx = AudioContext | null

let actx: MaybeCtx = null
let muted = false

function ensure(): MaybeCtx {
  if (actx) {
    if (actx.state === 'suspended') void actx.resume()
    return actx
  }
  try {
    const AC =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AC) return null
    actx = new AC()
  } catch {
    return null
  }
  return actx
}

function tone(f: number, t0: number, dur: number, type: OscillatorType, g: number): void {
  const a = actx
  if (!a || muted) return
  const o = a.createOscillator()
  const gn = a.createGain()
  o.type = type
  o.frequency.value = f
  o.connect(gn)
  gn.connect(a.destination)
  const t = a.currentTime + t0
  gn.gain.setValueAtTime(0.0001, t)
  gn.gain.exponentialRampToValueAtTime(g, t + 0.012)
  gn.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  o.start(t)
  o.stop(t + dur + 0.03)
}

/** Short filtered-noise "chip clink". */
function clink(t0: number, g: number): void {
  const a = actx
  if (!a || muted) return
  const n = Math.floor(a.sampleRate * 0.09)
  const buf = a.createBuffer(1, n, a.sampleRate)
  const d = buf.getChannelData(0)
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2)
  const src = a.createBufferSource()
  src.buffer = buf
  const bp = a.createBiquadFilter()
  bp.type = 'bandpass'
  bp.frequency.value = 2700
  bp.Q.value = 1.6
  const gn = a.createGain()
  gn.gain.value = g
  src.connect(bp)
  bp.connect(gn)
  gn.connect(a.destination)
  src.start(a.currentTime + t0)
}

export const raceSound = {
  /** Create/resume the AudioContext — call on a user gesture before any sound. */
  resume(): void {
    ensure()
  },
  setMuted(m: boolean): void {
    muted = m
    if (!m) ensure()
  },
  isMuted(): boolean {
    return muted
  },
  /** A two-note rising blip when the lead changes hands. */
  overtake(): void {
    ensure()
    tone(523, 0, 0.13, 'triangle', 0.08)
    tone(784, 0.07, 0.18, 'triangle', 0.07)
  },
  /** Win arpeggio + a few chip clinks, fired when the replay finishes. */
  win(): void {
    ensure()
    ;[523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.1, 0.5, 'triangle', 0.12))
    clink(0, 0.1)
    clink(0.13, 0.09)
    clink(0.27, 0.08)
  },
}
