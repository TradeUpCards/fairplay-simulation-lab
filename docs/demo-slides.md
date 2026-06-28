# Demo deck — transition slides for the Monday walkthrough

**Purpose:** the slides are *glue* between live screens. Each "TRANSITION" slide sets up the
next live segment; you cut to the app, demo it, then advance to the next slide. Built to be
rendered as walk-through **HTML slides** (hand this spec to Claude design).

**Audience:** cohort graders. **Mode:** run live (`:5173`) with these slides between beats.

**Source of truth:** the 5-part storyboard (Cory's version):
1. Thesis narration · 2. Standard-vs-FairPlay lobby + churn · 3. Dashboard (+ live table) ·
4. Pit-boss + AI investigator *(optional)* · 5. Training room *(optional)*.

---

## Design direction (for the HTML)

- **Match the app** so slides↔app feel continuous: dark ink background, **brass** (`#c79a4b`)
  accent, the FairPlay IQ wordmark, mono labels for small captions. The transition should feel
  like the same world dimming to a title, then back.
- **Few words per slide.** Big headline, ≤3 supporting lines. Detail lives in *speaker notes*,
  not on the slide.
- One persistent footer chip: `Synthetic data · illustrative, not a retention claim` (keeps the
  honesty guardrail visible the whole time).
- Keyboard walk-through (←/→). A small "▶ LIVE" marker on transition slides cues you to cut to
  the app.

---

## Slides

### 0 · Title
- **FairPlay Simulation Lab**
- Sub: *Telling unhealthy tables apart from normal poker — and explaining it safely.*
- Footer: operator copilot · synthetic data
- **Note:** One line on who/what. "An AI lab + operator copilot for online-poker table health."

### 1 · The problem
- Headline: **Some tables are quietly bad for the room.**
- Lines: Predation and collusion hide inside normal-looking play · Recreational players quietly
  churn · The room loses paid seat-time.
- **Note:** Set the stakes — it's not cheating headlines, it's slow bleed.

### 2 · The thesis  *(→ leads into Part 1/2)*
- Headline: **Healthier tables → more seat-time → both sides win.**
- Lines: Fairer seating keeps players in their seats longer · More paid seat-time for the
  platform · A better game for the players.
- **▶ LIVE next:** Player lobby.
- **Note:** "We'll show this two ways — first as a lobby you can feel, then as a sweep that tests
  whether it holds."

### 3 · TRANSITION → the lobby
- Headline: **One room. Two ways to seat it.**
- Lines: **Standard** fills the fullest table · **FairPlay** routes toward healthy tables ·
  Same players, different outcome.
- **▶ LIVE:** `:5173` → Player → **Pull back the curtain** → **Simulate room activity** (watch the
  re-rank); click a table → **Pit-boss** to reveal who's seated + table health.
- **Note:** Narrate the concentration vs spread; the seat-events drawer (health this round +
  estimated dwell). Keep "estimated" honest.

### 4 · TRANSITION → the dashboard
- Headline: **Does it hold at scale?**
- Lines: One room is an anecdote · Sweep across arrival rates **20 & 40**, multiple seeds and
  table counts · Total paid seat-time, saturation, hands.
- **▶ LIVE:** Sweep Dashboard (`#/dashboard`) — play the replay, scrub the regime heatmap.
- **Note:** The lobby room is *one cell* of this sweep (seed 42). Close on the regime line:
  **when FairPlay outperforms and when it doesn't.**

### 5 · TRANSITION → the pit-boss  *(optional — cut first if tight)*
- Headline: **When a table needs human eyes.**
- Lines: Structured scoring **flags** the risk · The AI **explains** it — carefully, never a
  verdict · A **human** decides. We never accuse or auto-enforce.
- **▶ LIVE:** Pit-boss console — a flagged case + the AI summary (counter-evidence + uncertainty
  visible).
- **Note:** This is the safety story: LLM explains, never detects. Surface counter-evidence out loud.

### 6 · TRANSITION → the training room  *(optional — quick or cut)*
- Headline: **The same eye, as a coach.**
- Lines: Sit at a 6-max table · A live AI coach reads each decision, guardrailed.
- **▶ LIVE:** Train tab — one hand + a coach card.
- **Note:** 60–90s max. Cut entirely if behind.

### 7 · Close
- Headline: **When FairPlay wins — and when it doesn't.**
- Lines: The result is **regime-dependent** (we show both) · Numbers are **illustrative**, not a
  retention claim · Guardrails hold: LLM never the detector · player/operator wall · no verdicts.
- **Note:** Recap the loop — *lobby recommendation → pit-boss review → sim evidence → eval*. End
  on the honesty: we'd rather show where it doesn't help than oversell.

---

## Open questions (to settle before design)
- Which optional beats are **in** for Monday — Part 4 (pit-boss), Part 5 (training), both, neither?
- Total time budget (drives how many transition slides vs. straight cuts)?
- Want a dedicated **guardrails** slide, or fold it into Close (slide 7)?
