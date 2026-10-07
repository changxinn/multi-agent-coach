import { useEffect } from 'react'
import { Alert, Button, Card, Col, Descriptions, Form, Input, InputNumber, Row, Skeleton, Space, Table, Tabs, Tag, Typography, message } from 'antd'
import { Dumbbell, RefreshCw } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDailyTrainingWorkout } from '@/pages/DashboardPage/useDailyTrainingWorkout'
import { api } from '@/lib/api'
import { ApiEndpoints } from '@/lib/constants/api'
import './TrainingPage.css'

const { Paragraph, Text, Title } = Typography
const trainingKey = ['training']

type Preferences = { equipment: string[]; training_days_per_week: number | null; session_duration_minutes: number | null; preferences: Record<string, unknown> }
type Workout = { id: number; occurred_at: string; description: string; duration_minutes: number | null; session_rpe: number | null; notes: string | null }
type Program = { id: number; version: number; goal: string; program: { days?: { day: string; focus: string; movements: string[] }[]; target_rpe?: string }; created_at: string }
type ExerciseGuidance = { name: string; guidance: string }

function TrainingTools() {
  const client = useQueryClient()
  const [messageApi, messageContextHolder] = message.useMessage()
  const [preferencesForm] = Form.useForm<Preferences>()
  const [logForm] = Form.useForm()
  const [adaptForm] = Form.useForm()
  const [searchForm] = Form.useForm<{ query: string }>()
  const preferences = useQuery({ queryKey: [...trainingKey, 'preferences'], queryFn: () => api.post<Preferences>(ApiEndpoints.Training.PreferencesGet, {}) })
  const programs = useQuery({ queryKey: [...trainingKey, 'programs'], queryFn: () => api.post<{ items: Program[] }>(ApiEndpoints.Training.ProgramsList, {}) })
  const workouts = useQuery({ queryKey: [...trainingKey, 'workouts'], queryFn: () => api.post<{ items: Workout[] }>(ApiEndpoints.Training.WorkoutsList, { days: 28, limit: 50 }) })
  const progress = useQuery({ queryKey: [...trainingKey, 'progress'], queryFn: () => api.post<{ workout_count: number; average_rpe: number | null; total_duration_minutes: number | null; last_workout_at: string | null; plateau_detected: boolean }>(ApiEndpoints.Training.Progress, { days: 28 }) })
  const savePreferences = useMutation({
    mutationFn: (values: Preferences) => api.post<Preferences>(ApiEndpoints.Training.PreferencesUpdate, values),
    onSuccess: (savedPreferences) => {
      client.setQueryData([...trainingKey, 'preferences'], savedPreferences)
      preferencesForm.setFieldsValue(savedPreferences)
      messageApi.success('Preferences saved.')
    },
    onError: (error: Error) => messageApi.error(error.message),
  })
  const logWorkout = useMutation({
    mutationFn: (values: Record<string, unknown>) => api.post(ApiEndpoints.Training.WorkoutsLog, values, { headers: { 'Idempotency-Key': globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}` } }),
    onSuccess: async () => {
      logForm.resetFields()
      messageApi.success('Workout saved.')
      await client.invalidateQueries({ queryKey: trainingKey })
    },
    onError: (error: Error) => messageApi.error(error.message),
  })
  const generate = useMutation({ mutationFn: () => api.post(ApiEndpoints.Training.ProgramsGenerate, {}), onSuccess: () => void client.invalidateQueries({ queryKey: [...trainingKey, 'programs'] }), onError: (error: Error) => messageApi.error(error.message) })
  const adapt = useMutation({ mutationFn: (values: { reason: string }) => api.post(ApiEndpoints.Training.ProgramsAdapt, values), onSuccess: () => { adaptForm.resetFields(); void client.invalidateQueries({ queryKey: [...trainingKey, 'programs'] }) }, onError: (error: Error) => messageApi.error(error.message) })
  const search = useMutation({ mutationFn: (values: { query: string }) => api.post<{ items: ExerciseGuidance[] }>(ApiEndpoints.Training.ExercisesSearch, values) })
  const error = [preferences, programs, workouts, progress].find(query => query.isError)?.error as Error | undefined

  useEffect(() => {
    if (preferences.data) preferencesForm.setFieldsValue(preferences.data)
  }, [preferences.data, preferencesForm])

  const submitLog = async () => {
    const values = await logForm.validateFields()
    logWorkout.mutate({ ...values, occurred_at: new Date(values.occurred_at).toISOString(), exercise_performance: [] })
  }

  return <section>
    {messageContextHolder}
    <Title level={3}>Manage your training</Title>
    {error && <Alert type="error" showIcon title={error.message} />}
    <Tabs items={[
      { key: 'recommendation', label: 'Live daily recommendation', children: <LiveWorkoutCard /> },
      { key: 'preferences', label: 'Preferences', children: <Card loading={preferences.isLoading}><Form form={preferencesForm} layout="vertical" onFinish={savePreferences.mutate}><Form.Item name="equipment" label="Equipment (comma separated)" getValueFromEvent={event => event.target.value.split(',').map((value: string) => value.trim()).filter(Boolean)} getValueProps={(value: string[]) => ({ value: value?.join(', ') ?? '' })}><Input placeholder="Dumbbells, bench, resistance bands" /></Form.Item><Row gutter={12}><Col span={12}><Form.Item name="training_days_per_week" label="Days per week"><InputNumber min={1} max={7} style={{ width: '100%' }} /></Form.Item></Col><Col span={12}><Form.Item name="session_duration_minutes" label="Session minutes"><InputNumber min={10} max={300} style={{ width: '100%' }} /></Form.Item></Col></Row><Button htmlType="submit" type="primary" loading={savePreferences.isPending}>Save preferences</Button></Form></Card> },
      { key: 'programs', label: 'Programs', children: <Space orientation="vertical" style={{ width: '100%' }}><Card extra={<Button type="primary" loading={generate.isPending} onClick={() => generate.mutate()}>Generate program</Button>} title="Program versions"><Table rowKey="id" loading={programs.isLoading} pagination={false} dataSource={programs.data?.items ?? []} columns={[{ title: 'Version', dataIndex: 'version' }, { title: 'Goal', dataIndex: 'goal' }, { title: 'Target RPE', render: (_, row: Program) => row.program.target_rpe ?? '—' }, { title: 'Created', dataIndex: 'created_at', render: value => new Date(value).toLocaleDateString() }]} /></Card><Card title="Adapt latest program"><Form form={adaptForm} layout="inline" onFinish={adapt.mutate}><Form.Item name="reason" rules={[{ required: true }]}><Input placeholder="Why should the plan change?" /></Form.Item><Button htmlType="submit" loading={adapt.isPending}>Adapt</Button></Form></Card></Space> },
      { key: 'log', label: 'Workout log', children: <Space orientation="vertical" style={{ width: '100%' }}><Card title="Log completed workout"><Form form={logForm} layout="vertical" onFinish={() => void submitLog()} initialValues={{ occurred_at: new Date().toISOString().slice(0, 16) }}><Form.Item name="description" label="Workout" rules={[{ required: true }]}><Input placeholder="Full body strength" /></Form.Item><Row gutter={12}><Col span={8}><Form.Item name="occurred_at" label="When" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item></Col><Col span={8}><Form.Item name="duration_minutes" label="Minutes"><InputNumber min={1} max={600} style={{ width: '100%' }} /></Form.Item></Col><Col span={8}><Form.Item name="session_rpe" label="Session RPE"><InputNumber min={1} max={10} step={0.5} style={{ width: '100%' }} /></Form.Item></Col></Row><Form.Item name="notes" label="Notes"><Input.TextArea /></Form.Item><Button htmlType="submit" type="primary" loading={logWorkout.isPending}>Save workout</Button></Form></Card><Card title="Recent workouts"><Table rowKey="id" loading={workouts.isLoading} pagination={false} dataSource={workouts.data?.items ?? []} columns={[{ title: 'Date', dataIndex: 'occurred_at', render: value => new Date(value).toLocaleDateString() }, { title: 'Workout', dataIndex: 'description' }, { title: 'Minutes', dataIndex: 'duration_minutes' }, { title: 'RPE', dataIndex: 'session_rpe' }]} /></Card></Space> },
      { key: 'progress', label: 'Progress', children: <Card loading={progress.isLoading}><Descriptions column={{ xs: 1, sm: 2 }}><Descriptions.Item label="Workouts (28 days)">{progress.data?.workout_count ?? 0}</Descriptions.Item><Descriptions.Item label="Total minutes">{progress.data?.total_duration_minutes ?? 0}</Descriptions.Item><Descriptions.Item label="Average RPE">{progress.data?.average_rpe ?? '—'}</Descriptions.Item><Descriptions.Item label="Last workout">{progress.data?.last_workout_at ? new Date(progress.data.last_workout_at).toLocaleDateString() : 'None logged'}</Descriptions.Item></Descriptions>{progress.data?.plateau_detected && <Alert type="info" showIcon title="High recent effort detected" description="Consider adapting your program or prioritizing recovery." />}</Card> },
      { key: 'guidance', label: 'Exercise guidance', children: <Card><Form form={searchForm} layout="inline" onFinish={search.mutate}><Form.Item name="query" rules={[{ required: true }]}><Input placeholder="Search an exercise" /></Form.Item><Button htmlType="submit" loading={search.isPending}>Search</Button></Form><div className="training-live-content">{search.isError && <Alert type="error" showIcon title="Unable to get exercise guidance" description={(search.error as Error).message} />}{search.data?.items.map(item => <Alert key={item.name} type="info" title={item.name} description={item.guidance} showIcon />)}{search.data && search.data.items.length === 0 && <Alert type="info" showIcon title="No exercise guidance found" description="Try another exercise name." />}</div></Card> },
    ]} />
  </section>
}

function LiveWorkoutCard() {
  const { workout, refresh } = useDailyTrainingWorkout()
  const isLoading = workout.isLoading || refresh.isPending
  let content
  if (isLoading) content = <Skeleton active paragraph={{ rows: 6 }} />
  else if (workout.isError || !workout.data) content = <Alert type="warning" showIcon title="Today’s workout is temporarily unavailable." action={<Button size="small" onClick={() => void workout.refetch()}>Retry</Button>} />
  else {
    const { data } = workout
    content = <Space orientation="vertical" size="middle" style={{ width: '100%' }}><div className="training-workout-heading"><div><Text strong>{data.title}</Text><div><Text type="secondary">Recovery status: {data.recovery_status.replace('_', ' ')}</Text></div></div><Tag color={data.status === 'recovery_adjusted' ? 'orange' : 'green'}>{data.status === 'recovery_adjusted' ? 'Recovery adjusted' : 'Ready'}</Tag></div><Paragraph className="training-workout-text">{data.workout_text}</Paragraph>{data.recovery_note && <Alert type={data.status === 'recovery_adjusted' ? 'warning' : 'info'} showIcon title={data.recovery_note} />}<Text type="secondary" className="training-generated-at">{data.reused ? 'Reused today’s saved recommendation' : 'Generated a new recommendation'} · {new Date(data.generated_at).toLocaleString()}</Text></Space>
  }
  return <Card title={<div className="flex flex-row gap-2"><Dumbbell size={19} /><span className="training-card-title">Live daily recommendation</span></div>} extra={<Button icon={<RefreshCw size={16} />} loading={refresh.isPending} onClick={() => refresh.mutate()}>Generate new plan</Button>}><Text type="secondary">Uses your saved training profile and the authoritative Recovery status for today.</Text><div className="training-live-content">{content}</div></Card>
}

export function TrainingPage() {
  return <div className="training-page"><section className="training-hero"><Title level={2}>Training</Title><Paragraph>Use your training profile and Recovery guidance to create practical exercise support for today.</Paragraph></section><TrainingTools /></div>
}