// @vitest-environment happy-dom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { OperatorNav } from '../src/components/OperatorNav'

afterEach(cleanup)

describe('OperatorNav — operator sub-nav (Console · Simulator · Eval)', () => {
  it('renders the three demo-spine tabs in order', () => {
    render(<OperatorNav view="console" onViewChange={() => {}} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual([
      'ConsolePit-boss review',
      'SimulatorStandard vs FairPlay',
      'EvalEvidence & proof',
    ])
  })

  it('marks only the active view as selected (aria-selected)', () => {
    render(<OperatorNav view="simulator" onViewChange={() => {}} />)
    expect(screen.getByRole('tab', { name: /Simulator/ }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tab', { name: /Console/ }).getAttribute('aria-selected')).toBe('false')
    expect(screen.getByRole('tab', { name: /Eval/ }).getAttribute('aria-selected')).toBe('false')
  })

  it('fires onViewChange with the clicked view id', () => {
    const onViewChange = vi.fn()
    render(<OperatorNav view="console" onViewChange={onViewChange} />)
    fireEvent.click(screen.getByRole('tab', { name: /Eval/ }))
    expect(onViewChange).toHaveBeenCalledWith('eval')
  })
})
