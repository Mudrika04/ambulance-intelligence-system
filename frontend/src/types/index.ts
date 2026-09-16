export type FsmState = 'NORMAL' | 'PREPARE' | 'ALL_RED' | 'EMERGENCY_GREEN' | 'CLEARANCE'
export type Lamp = 'RED' | 'YELLOW' | 'GREEN'
export type Direction = 'NORTH' | 'SOUTH' | 'EAST' | 'WEST'

export interface Decision {
  decision: 'PRIORITY_REQUESTED' | 'MONITORING' | 'NO_PRIORITY'
  reason_codes: string[]
  reasons: string[]
  track_id: number | null
  approach: string
  priority_score: number
  threshold: number
}

export interface PriorityBreakdown {
  score: number
  threshold: number
  exceeds_threshold: boolean
  components: Record<string, number>
  weights: Record<string, number>
  contributions: Record<string, number>
}

export interface Ambulance {
  track_id: number
  bbox: number[]
  confidence: number
  approach: string
  zone: string
  in_roi: boolean
  direction: string
  motion_state: string
  proximity: string
  relative_eta_s: number | null
  proximity_note: string
  validated: boolean
  validation: { frames: number; required_frames: number; validated: boolean; failures: string[] }
  priority: PriorityBreakdown
  decision: Decision
  confidence_history: number[]
  trajectory: number[][]
  simulated: boolean
}

export interface SignalSnapshot {
  fsm: {
    state: FsmState
    priority_approach: string | null
    track_id: number | null
    phase_elapsed: number
    phase_duration: number
    remaining: number
    emergency_active: boolean
    rejected_requests: number
  }
  lights: Record<Direction, Lamp>
  simulated: boolean
  note: string
}

export interface CorridorNode {
  id: string
  name: string
  role: string
  status: 'MONITOR' | 'PREPARE' | 'ACTIVE_PRIORITY' | 'CLEARED'
}

export interface MetricSummary {
  mean: number | null
  p95: number | null
  last: number | null
  samples: number
}

export interface SystemState {
  running: boolean
  mode: string
  simulated: boolean
  frame_id: number
  timestamp: number
  resolution?: number[]
  source_status?: string
  ambulances: Ambulance[]
  other_detections: number
  decision: Decision | null
  focus_track: number | null
  signal: SignalSnapshot
  green_corridor: { label?: string; simulated: boolean; intersections: CorridorNode[] }
  health: Record<string, string>
  metrics: Record<string, MetricSummary | number | boolean>
  errors?: string[]
}

export interface TimelineEvent {
  id?: number
  timestamp: string | number
  event_type: string
  level?: string
  track_id?: number | null
  message?: string
  metadata?: Record<string, unknown>
}
