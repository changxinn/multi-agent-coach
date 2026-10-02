export type NutritionStatus = 'available' | 'no_target' | 'unavailable'
export type RecoveryStatus = 'green' | 'amber' | 'red' | 'escalate' | 'no_assessment' | 'unavailable'
export type ActionSeverity = 'critical' | 'warning' | 'info'

export interface NutritionTrendPoint {
  date: string
  calorie_adherence_pct: number | null
  protein_adherence_pct: number | null
  meal_count: number
}

export interface RecoveryTrendPoint {
  date: string
  sleep_duration_minutes: number | null
  sleep_quality: number | null
  assessment_status: Exclude<RecoveryStatus, 'no_assessment' | 'unavailable'> | null
  assessment_score: number | null
}

export interface TrainingSnapshot {
  status: 'unavailable'
  message: string
  last_activity_at: string | null
}

export interface DailyTrainingWorkout {
  status: 'ready' | 'recovery_adjusted' | 'unavailable'
  title: string
  workout_text: string
  recovery_note: string | null
  recovery_status: RecoveryStatus
  generated_at: string
  reused: boolean
}

export interface NutritionSnapshot {
  status: NutritionStatus
  message: string | null
  calories: number | null
  protein_g: number | null
  meal_count: number | null
  calorie_target_kcal: number | null
  protein_target_g: number | null
  remaining_calories: number | null
  remaining_protein_g: number | null
  calorie_adherence_pct: number | null
  protein_adherence_pct: number | null
  trend: NutritionTrendPoint[]
}

export interface RecoverySnapshot {
  status: RecoveryStatus
  message: string | null
  assessment_score: number | null
  assessment_created_at: string | null
  sleep_duration_minutes: number | null
  sleep_quality: number | null
  sleep_logged_at: string | null
  energy: number | null
  soreness: number | null
  stress: number | null
  check_in_created_at: string | null
  trend: RecoveryTrendPoint[]
}

export interface DashboardAction {
  id: string
  priority: number
  severity: ActionSeverity
  title: string
  description: string
  route: '/chat' | '/nutrition' | '/recovery-table'
}

export interface DailyCommandCenterResponse {
  generated_at: string
  dashboard_date: string
  training: TrainingSnapshot
  nutrition: NutritionSnapshot
  recovery: RecoverySnapshot
  actions: DashboardAction[]
  errors: { domain: 'nutrition' | 'recovery'; message: string }[]
}