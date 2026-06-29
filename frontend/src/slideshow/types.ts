import type { ComponentType } from 'react'

/**
 * One slide in the presentation deck.
 *
 * A slide is just a React component plus a little metadata. Because it's a
 * component (not static markup), a slide can use hooks and embed live app
 * pieces — the dashboard's replay chart, a seat ring, anything — when you're
 * ready to go beyond static content.
 *
 * To add a slide, see `src/slideshow/README.md`. The short version:
 *   1. create `src/slideshow/slides/<your-slide>.tsx`
 *   2. export a `SlideDef` from it
 *   3. add it (in the order you want) to the array in `slides/index.ts`
 */
export interface SlideDef {
  /** Stable, URL-safe id. Used for React keys and `#/slideshow/<n>` deep links. */
  id: string
  /** Short label for the progress rail / speaker reference. Optional. */
  label?: string
  /** The slide body. Wrap your content in <Slide> to get the branded frame. */
  Component: ComponentType
  /** Opt out of the deck's readable-width cap and use the full stage width.
   *  For slides that embed a live app view (the lobby board, the curtain) that
   *  wants every pixel — text slides should leave this off. */
  wide?: boolean
}
