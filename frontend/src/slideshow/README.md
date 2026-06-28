# Presentation deck (`#/slideshow`)

A full-screen pitch deck built into the app, styled with the FairPlay IQ tokens.
Open it from the header **Slideshow** button or at `#/slideshow` (deep-link a page
with `#/slideshow/3`).

**Navigation:** `←` / `→` (also `Space`, `PageUp`/`PageDown`) move between slides,
`Home` / `End` jump to the ends, `Esc` exits back to the app. The progress dots and
the on-screen arrows do the same thing.

## How it fits together

| File | Role |
| --- | --- |
| `src/views/Slideshow.tsx` | The deck shell — chrome, keyboard/click nav, page numbers, URL sync. You rarely touch this. |
| `src/slideshow/types.ts` | The `SlideDef` type. |
| `src/slideshow/Slide.tsx` | The authoring kit: `Slide`, `Stat`, `Card`, `Lead`, `Pill`, `Bullets`, `Columns`, `Cite`, `Placeholder`. |
| `src/slideshow/slides/*.tsx` | One file per slide. |
| `src/slideshow/slides/index.ts` | The ordered `SLIDES` array — **this is the deck order.** |

## Add a slide (the whole job)

1. **Create** `src/slideshow/slides/my-slide.tsx`:

   ```tsx
   import { Slide, Lead, Bullets } from '../Slide'
   import type { SlideDef } from '../types'

   function MySlide() {
     return (
       <Slide kicker="Section" title="My headline">
         <Lead>The one thing the room should read.</Lead>
         <Bullets items={['First point', 'Second point']} />
       </Slide>
     )
   }

   export const mySlide: SlideDef = { id: 'my-slide', label: 'My slide', Component: MySlide }
   ```

2. **Register** it in `slides/index.ts` — add the import and drop it into the
   `SLIDES` array where you want it to appear.

That's it. The shell handles everything else.

## Tips

- A slide is a real React component, so it can use hooks and **embed live app
  pieces** — e.g. drop `<SweepReplayChart .../>` or a `<SeatRing .../>` straight
  into a slide when you want the real thing instead of a placeholder.
- Wrap content in `<Slide center>` for title/statement slides (vertically
  centered); omit `center` for content slides (top-aligned).
- Use `<Placeholder>` for a "drop your view here" panel until real content lands.
- Style stays on-brand if you compose the kit. If you go custom, the tokens are
  `bg-surface`, `border-line`, `text-brass`, `text-muted`, `font-mono`, etc.
  (see `src/styles.css`).
- House style: **no semicolons, single quotes, ~100 col.** After editing run
  `npx prettier --write --no-semi --single-quote --print-width 100 <files>`.
