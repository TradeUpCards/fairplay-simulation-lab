import { describe, it, expect } from 'vitest'
import { createSimStore } from '../src/state/simStore'

describe('simStore', () => {
  it('starts at standard / hour 0 / adherence 0', () => {
    const s = createSimStore()
    expect(s.getState()).toEqual({ path: 'standard', hour: 0, adherence: 0 })
  })

  it('honors an initial override', () => {
    const s = createSimStore({ path: 'fairplay', hour: 4 })
    expect(s.getState()).toEqual({ path: 'fairplay', hour: 4, adherence: 0 })
  })

  it('notifies a subscriber once per mutation and reflects new state', () => {
    const s = createSimStore()
    const seen: number[] = []
    const unsub = s.subscribe((st) => seen.push(st.hour))

    s.setHour(3)
    s.setAdherence(50)
    s.setPath('fairplay')

    expect(seen).toHaveLength(3)
    expect(s.getState()).toEqual({ path: 'fairplay', hour: 3, adherence: 50 })

    unsub()
    s.setHour(5)
    expect(seen).toHaveLength(3) // no notification after unsubscribe
    expect(s.getState().hour).toBe(5)
  })

  it('advanceHour increments and clamps at the 8-hour horizon', () => {
    const s = createSimStore({ hour: 7 })
    s.advanceHour()
    expect(s.getState().hour).toBe(8)
    s.advanceHour()
    expect(s.getState().hour).toBe(8)
  })

  it('clamps hour to [0,8] and adherence to [0,100]', () => {
    const s = createSimStore()
    s.setHour(-2)
    expect(s.getState().hour).toBe(0)
    s.setHour(99)
    expect(s.getState().hour).toBe(8)
    s.setAdherence(-10)
    expect(s.getState().adherence).toBe(0)
    s.setAdherence(250)
    expect(s.getState().adherence).toBe(100)
  })

  it('rounds fractional hours to integers', () => {
    const s = createSimStore()
    s.setHour(3.7)
    expect(s.getState().hour).toBe(4)
  })

  it('fans out to multiple independent subscribers', () => {
    const s = createSimStore()
    let a = 0
    let b = 0
    s.subscribe(() => {
      a += 1
    })
    const unsubB = s.subscribe(() => {
      b += 1
    })

    s.setHour(1)
    unsubB()
    s.setHour(2)

    expect(a).toBe(2)
    expect(b).toBe(1)
  })

  it('reset returns to defaults and notifies', () => {
    const s = createSimStore({ path: 'fairplay', hour: 6, adherence: 80 })
    let notified = 0
    s.subscribe(() => {
      notified += 1
    })
    s.reset()
    expect(s.getState()).toEqual({ path: 'standard', hour: 0, adherence: 0 })
    expect(notified).toBe(1)
  })
})
