import { Alert, Button, Card, Skeleton, Space, Tooltip, Typography } from 'antd'
import { Dumbbell } from 'lucide-react'
import { ReloadOutlined } from '@ant-design/icons'
import { useDailyTrainingWorkout } from './useDailyTrainingWorkout'

const { Text } = Typography

const workoutTerms = [
  { abbreviation: 'RPE', pattern: /\bRPE\b/i, definition: 'Rate of Perceived Exertion (RPE) describes how hard a set feels on a scale from 1 to 10. RPE 7 is challenging but controlled, with roughly three good-form repetitions left.' },
  { abbreviation: 'AMRAP', pattern: /\bAMRAP\b/i, definition: 'As Many Rounds or Repetitions As Possible (AMRAP) means completing as much quality work as you can in the stated time.' },
  { abbreviation: 'EMOM', pattern: /\bEMOM\b/i, definition: 'Every Minute on the Minute (EMOM) means starting the prescribed work at the beginning of each minute, then resting for the remainder.' },
  { abbreviation: 'HIIT', pattern: /\bHIIT\b/i, definition: 'High-Intensity Interval Training (HIIT) alternates short hard-effort intervals with recovery periods.' },
  { abbreviation: 'RM', pattern: /\b\d+\s*RM\b/i, definition: 'Repetition Maximum (RM) is the heaviest weight you can lift for a specified number of repetitions, such as a 5RM.' },
  { abbreviation: 'DB', pattern: /\bDB\b/i, definition: 'Dumbbell (DB) is a handheld weight, usually used one in each hand or one at a time.' },
  { abbreviation: 'KB', pattern: /\bKB\b/i, definition: 'Kettlebell (KB) is a handled weight with a rounded base.' },
  { abbreviation: 'BW', pattern: /\bBW\b/i, definition: 'Bodyweight (BW) means using your own body as resistance rather than external weights.' },
]

function definitionsFor(workoutText: string) {
  return workoutTerms.filter(term => term.pattern.test(workoutText))
}

export function TrainingStatusCard() {
  const { workout, refresh } = useDailyTrainingWorkout()
  const isLoading = workout.isLoading || refresh.isPending
  const definitions = workout.data ? definitionsFor(workout.data.workout_text) : []
  const shouldShowGuidance = Boolean(
    workout.data && (workout.data.recovery_note || definitions.length > 0),
  )
  const guidance = shouldShowGuidance && workout.data ? (
    <div className="dashboard-training-guidance">
      {workout.data.recovery_note && <div>{workout.data.recovery_note}</div>}
      {definitions.map(term => <div key={term.abbreviation}>{term.definition}</div>)}
    </div>
  ) : null
  const hasBottomGuidance = !isLoading && guidance != null
  return (
    <Card
      className="dashboard-agent-card dashboard-training-card"
      title={<span><Dumbbell size={18} className="dashboard-agent-icon training" /> Training Planner</span>}
      extra={<Tooltip title="Generate a new plan for today"><Button type="link" aria-label="Generate a new plan for today" icon={<ReloadOutlined />} loading={refresh.isPending} onClick={() => refresh.mutate()} /></Tooltip>}
    >
      <Space className={`dashboard-agent-content${hasBottomGuidance ? ' dashboard-agent-content--has-guidance' : ''}`} orientation="vertical" size="middle" style={{ width: '100%' }}>
        {isLoading ? <Skeleton active paragraph={{ rows: 5 }} /> : workout.isError || !workout.data ? <Alert type="warning" showIcon title="Today’s workout is temporarily unavailable." action={<Button size="small" onClick={() => void workout.refetch()}>Retry</Button>} /> : <>
          <Text strong>{workout.data.title}</Text>
          <Text className="dashboard-training-workout">{workout.data.workout_text}</Text>
          {guidance && <div className="dashboard-training-guidance-container"><Alert className="dashboard-training-guidance-alert" type={workout.data.status === 'recovery_adjusted' ? 'warning' : 'info'} showIcon message={guidance} /></div>}
        </>}
      </Space>
    </Card>
  )
}