import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DecisionPanel } from '../DecisionPanel'
import { AmbulancePanel } from '../AmbulancePanel'
import type { Ambulance, Decision } from '../../types'

const decision: Decision = {
  decision: 'PRIORITY_REQUESTED',
  reason_codes: ['AMBULANCE_DETECTED', 'TRACK_PERSISTENT', 'BELOW_THRESHOLD'],
  reasons: ['Ambulance detected', 'Persistent tracking across frames', 'Priority score below the configured threshold'],
  track_id: 3,
  approach: 'NORTH',
  priority_score: 0.81,
  threshold: 0.7,
}

describe('DecisionPanel', () => {
  it('lists every reason code with a positive or negative marker', () => {
    render(<DecisionPanel decision={decision} ambulances={[]} />)
    expect(screen.getByText('Priority requested')).toBeInTheDocument()
    expect(screen.getByText('Ambulance detected')).toBeInTheDocument()
    expect(screen.getAllByText('✓')).toHaveLength(2)
    expect(screen.getAllByText('×')).toHaveLength(1)
  })

  it('shows an empty state rather than inventing a decision', () => {
    render(<DecisionPanel decision={null} ambulances={[]} />)
    expect(screen.getByText(/Nothing to explain yet/)).toBeInTheDocument()
  })
})

describe('AmbulancePanel', () => {
  it('reports runtime values for the highest scoring track', () => {
    const ambulance = {
      track_id: 7,
      bbox: [0, 0, 10, 10],
      confidence: 0.91,
      approach: 'NORTH',
      zone: 'NEAR_ZONE',
      in_roi: true,
      direction: 'INBOUND',
      motion_state: 'APPROACHING',
      proximity: 'NEAR',
      relative_eta_s: 5.4,
      proximity_note: 'Camera-based relative ETA estimate',
      validated: true,
      validation: { frames: 5, required_frames: 5, validated: true, failures: [] },
      priority: {
        score: 0.86,
        threshold: 0.7,
        exceeds_threshold: true,
        components: { detection_confidence: 0.91 },
        weights: { detection_confidence: 0.2 },
        contributions: { detection_confidence: 0.18 },
      },
      decision,
      confidence_history: [0.9],
      trajectory: [],
      simulated: true,
    } as unknown as Ambulance
    render(<AmbulancePanel ambulances={[ambulance]} />)
    expect(screen.getByText('#7')).toBeInTheDocument()
    expect(screen.getByText('0.91')).toBeInTheDocument()
    expect(screen.getByText('5.4 s')).toBeInTheDocument()
    expect(screen.getByText('5/5 frames')).toBeInTheDocument()
  })

  it('does not claim a detection when nothing is tracked', () => {
    render(<AmbulancePanel ambulances={[]} />)
    expect(screen.getByText(/No ambulance is currently tracked/)).toBeInTheDocument()
  })
})
