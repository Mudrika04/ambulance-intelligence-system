import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PhaseRibbon } from '../PhaseRibbon'
import { SignalPanel } from '../SignalPanel'
import type { SignalSnapshot } from '../../types'

const snapshot = (state: SignalSnapshot['fsm']['state'], approach: string | null): SignalSnapshot => ({
  fsm: {
    state,
    priority_approach: approach,
    track_id: 7,
    phase_elapsed: 1,
    phase_duration: 4,
    remaining: 3,
    emergency_active: state !== 'NORMAL',
    rejected_requests: 0,
  },
  lights:
    state === 'EMERGENCY_GREEN'
      ? { NORTH: 'GREEN', SOUTH: 'RED', EAST: 'RED', WEST: 'RED' }
      : { NORTH: 'RED', SOUTH: 'RED', EAST: 'RED', WEST: 'RED' },
  simulated: true,
  note: 'simulated',
})

describe('PhaseRibbon', () => {
  it('shows every phase of the state machine', () => {
    render(<PhaseRibbon signal={snapshot('PREPARE', 'NORTH')} />)
    for (const phase of ['NORMAL', 'PREPARE', 'ALL RED', 'EMERGENCY GREEN', 'CLEARANCE']) {
      expect(screen.getByText(phase)).toBeInTheDocument()
    }
  })

  it('names the priority approach', () => {
    render(<PhaseRibbon signal={snapshot('EMERGENCY_GREEN', 'NORTH')} />)
    expect(screen.getByText('NORTH')).toBeInTheDocument()
  })
})

describe('SignalPanel', () => {
  it('gives green to the priority approach only', () => {
    render(<SignalPanel signal={snapshot('EMERGENCY_GREEN', 'NORTH')} />)
    expect(screen.getByLabelText('NORTH GREEN on')).toBeInTheDocument()
    expect(screen.getByLabelText('SOUTH RED on')).toBeInTheDocument()
    expect(screen.getByLabelText('EAST GREEN off')).toBeInTheDocument()
  })
})
