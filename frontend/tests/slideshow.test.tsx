// @vitest-environment happy-dom
import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { Slideshow } from '../src/views/Slideshow'
import { SLIDES } from '../src/slideshow/slides'

const N = SLIDES.length
const page = (i: number) => `${i} / ${N}`

// The deck mirrors its position to window.location.hash; reset it between tests
// so each render starts on slide 1.
beforeEach(() => window.history.replaceState(null, '', '#/slideshow'))
afterEach(cleanup)

describe('Slideshow — presentation deck shell', () => {
  it('starts on the first slide with the previous control disabled', () => {
    render(<Slideshow />)
    expect(screen.getByText(page(1))).toBeTruthy()
    expect(screen.getByLabelText('Previous slide').hasAttribute('disabled')).toBe(true)
  })

  it('advances and retreats with the arrow keys', () => {
    render(<Slideshow />)
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.getByText(page(2))).toBeTruthy()
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(screen.getByText(page(1))).toBeTruthy()
  })

  it('clamps at the first slide when going back from the start', () => {
    render(<Slideshow />)
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(screen.getByText(page(1))).toBeTruthy()
  })

  it('advances and retreats with the on-screen controls', () => {
    render(<Slideshow />)
    fireEvent.click(screen.getByLabelText('Next slide'))
    expect(screen.getByText(page(2))).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Previous slide'))
    expect(screen.getByText(page(1))).toBeTruthy()
  })

  it('jumps to the last slide via End and disables the next control there', () => {
    render(<Slideshow />)
    fireEvent.keyDown(window, { key: 'End' })
    expect(screen.getByText(page(N))).toBeTruthy()
    expect(screen.getByLabelText('Next slide').hasAttribute('disabled')).toBe(true)
  })

  it('keeps the deck chrome (logo + exit) across slides', () => {
    render(<Slideshow />)
    // Advance off the title slide (which has its own logo) so only the
    // persistent top-rail logo remains.
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.getByAltText('FairPlay IQ')).toBeTruthy()
    expect(screen.getByText(/Exit/)).toBeTruthy()
  })
})
