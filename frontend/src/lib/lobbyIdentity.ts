/**
 * Deterministic, player-safe identity synthesis for the lobby demo.
 *
 * The frozen room data carries only aggregate `composition` (archetype counts) per
 * table — no per-seat handle, face, stack, or dwell forecast. For the demo we
 * synthesize those *deterministically* (seeded by id) so they're stable across
 * renders and rehearsals — the same posture as the already-synthesized poker-stat
 * columns (avg pot / hands-hr). Illustrative, never a claim.
 *
 * Guardrail: nothing here reads or returns an archetype. Faces/handles are keyed to
 * *identity*, never classification — so a face can never leak "shark" into the
 * player view. Archetype is layered on separately, operator-side only.
 */

/** Stable unsigned 32-bit hash of a string (FNV-1a-ish). Deterministic. */
export function seedInt(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

// Avatar casts — auto-loaded from assets/avatars/<set>/ at build time. Zero files →
// empty (callers fall back to the emoji seat). Drop nano-banana JPEGs in to light up.
const sortedEntries = (g: Record<string, string>): { stem: string; url: string }[] =>
  Object.keys(g)
    .sort()
    .map((p) => ({ stem: p.split('/').pop()?.replace(/\.\w+$/, '') ?? p, url: g[p] }))

// Identity faces — realistic + film portraits mixed into ONE pool, assigned to
// players by identity hash (no toggle). Drop more JPGs into either folder to extend
// the cast. Zero files → empty (callers fall back to the emoji seat).
const FACE_ENTRIES = [
  ...sortedEntries(
    import.meta.glob('../assets/avatars/realistic/*.{jpg,jpeg,png,webp}', {
      eager: true,
      import: 'default',
    }) as Record<string, string>,
  ),
  ...sortedEntries(
    import.meta.glob('../assets/avatars/film/*.{jpg,jpeg,png,webp}', {
      eager: true,
      import: 'default',
    }) as Record<string, string>,
  ),
]
const FACES = FACE_ENTRIES.map((e) => e.url)
const URL_TO_STEM: Record<string, string> = {}
for (const e of FACE_ENTRIES) URL_TO_STEM[e.url] = e.stem

// Some faces get a handle that *fits* the character (the film cast especially), so a
// recognizable face reads with a fitting name. Keyed by file stem; evocative, not
// exact trademarks. Faces are still assigned by identity (not archetype) — a themed
// handle is flavor, never a classification.
const THEMED_HANDLE: Record<string, string> = {
  'film-01': 'MartiniShaken',
  'film-02': 'ArcReactor',
  'film-03': 'HighNoon',
  'film-04': 'WhySoSerious',
  'film-05': 'DarkSideRaise',
  'film-06': 'TheDanger',
  'film-07': 'TheDon',
  'film-08': 'PinstripeAl',
  'film-09': 'LilFriend',
  'film-10': 'LosPollos',
  'film-11': 'NumberOne',
  'film-12': 'FedoraWhip',
  'avatar-01': 'DustyTrail',
  'avatar-03': 'AlohaWhale',
  'avatar-05': 'GranGrinder',
  'avatar-07': 'SolverSam',
}

// Cartoon set is keyed by archetype (filename == archetype), used as the small
// pit-boss "reveal" badge pinned on a seat — NOT as an identity face.
const CARTOON_GLOB = import.meta.glob('../assets/avatars/cartoon/*.{jpg,jpeg,png,webp}', {
  eager: true,
  import: 'default',
}) as Record<string, string>
const CARTOON_BY_ARCH: Record<string, string> = {}
for (const [path, url] of Object.entries(CARTOON_GLOB)) {
  const name = path.split('/').pop()?.replace(/\.\w+$/, '')
  if (name) CARTOON_BY_ARCH[name] = url
}

/** A stable identity-face URL for a player (mixed realistic+film pool), or null. */
export function avatarFor(id: string): string | null {
  if (FACES.length === 0) return null
  return FACES[seedInt(id) % FACES.length]
}

/** The small cartoon archetype badge (pit-boss reveal), or null if none installed. */
export function archetypeBadge(archetype?: string | null): string | null {
  if (!archetype) return null
  return CARTOON_BY_ARCH[archetype] ?? null
}

// Neutral, fun poker handles — no archetype signal. Assigned by identity seed.
const HANDLES = [
  'RiverRat', 'ChipMonk', 'BluffCity', 'NitWit', 'AllInAda', 'CoolHandLuke',
  'SnapCall', 'TiltProof', 'FeltFox', 'GutShotGus', 'PocketAce', 'RoundedUp',
  'SlowRoller', 'BigStackBea', 'DealMeIn', 'TheRegular', 'CardsUp', 'OpenLimper',
  'ValueTown', 'BackdoorBob', 'StoneCold', 'FlopHouse', 'TurnedNuts', 'RailBird',
]

/** A stable display handle for an identity. If the player's assigned face is one of
 *  the themed faces, use the handle that fits it; otherwise a stable generic handle. */
export function handleFor(id: string): string {
  const url = avatarFor(id)
  const stem = url ? URL_TO_STEM[url] : undefined
  if (stem && THEMED_HANDLE[stem]) return THEMED_HANDLE[stem]
  return HANDLES[seedInt(id) % HANDLES.length]
}

/** A stable, plausible stack in whole dollars (illustrative). */
export function stackFor(id: string): number {
  const n = seedInt(id + ':stack')
  // $80–$1280, rounded to a tidy $5.
  return 80 + Math.round(((n % 1200) / 5)) * 5
}

// Archetype → a rough average dwell baseline (minutes). Mirrors the spread in
// players.json avg_session_minutes; used only operator-side (forecast in the curtain).
const DWELL_BASE: Record<string, number> = {
  new: 18,
  recreational: 65,
  promo_hunter: 30,
  regular: 80,
  grinder: 130,
  aggressive_predatory: 150,
  solver_like: 140,
  healthy_anchor: 110,
  cluster_member: 95,
  shared_device_household: 70,
  bot_like: 200,
}

/**
 * Illustrative sit-duration forecast (minutes). Heuristic, not a trained model:
 * an archetype dwell baseline + seeded jitter, then modulated by the *table's
 * computed health* when provided — healthier table → longer expected sit (the
 * FairPlay thesis). The health term is the real engine score; the mapping to
 * minutes is illustrative. Operator-side (it leans on archetype).
 */
export function forecastFor(
  id: string,
  archetype?: string | null,
  tableHealth?: number | null,
): number {
  const base = DWELL_BASE[archetype ?? ''] ?? 60
  const jitter = (seedInt(id + ':dwell') % 41) - 20 // ±20 min
  // health 0→100 maps to ×0.7→×1.3 (neutral ×1 at ~50). Undefined health = ×1.
  const hm =
    tableHealth == null ? 1 : 0.7 + 0.6 * (Math.max(0, Math.min(100, tableHealth)) / 100)
  return Math.max(8, Math.round(((base + jitter) * hm) / 5) * 5)
}

export interface SyntheticSeat {
  /** stable synthetic identity id for this seat (drives face/handle/stack/forecast) */
  id: string
  /** the seat's archetype — OPERATOR-SIDE ONLY; never render in the player view. */
  archetype: string
}

/**
 * Expand an aggregate `composition` ({archetype, count}[]) into per-seat synthetic
 * identities, deterministically ordered by table. Each seat gets a stable id so its
 * face/handle/stack are consistent across renders and across the two sidecar views.
 */
export function expandSeats(
  tableId: string,
  composition: { archetype: string; count: number }[],
): SyntheticSeat[] {
  const seats: SyntheticSeat[] = []
  let i = 0
  for (const c of composition) {
    for (let k = 0; k < c.count; k++) {
      seats.push({ id: `${tableId}-seat-${i}`, archetype: c.archetype })
      i++
    }
  }
  return seats
}
