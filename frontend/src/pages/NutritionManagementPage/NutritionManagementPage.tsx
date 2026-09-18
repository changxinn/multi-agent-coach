import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Spin, Statistic, Table, Tabs, Tag, Typography } from 'antd'
import { nutritionManagementApi, type Meal, type Profile, type Target } from '@/lib/nutrition-management-api'

const { Title, Text } = Typography
const initialProfile: Profile = { timezone: 'Asia/Singapore', dietary_preference: 'omnivore', meals_per_day: 3, activity_level: 'moderate', age: null, gender: null, weight_kg: null, height_cm: null, dietary_restrictions: [], allergies: [] }

export function NutritionManagementPage() {
  const [profile, setProfile] = useState<Profile>(initialProfile)
  const [meals, setMeals] = useState<Meal[]>([])
  const [target, setTarget] = useState<Target | null>(null)
  const [foods, setFoods] = useState<Array<{ fdc_id: number; name: string; calories: number | null }>>([])
  const [assessments, setAssessments] = useState<Array<{ id: number; status: string; score: number; message: string; recommendations: string[]; created_at: string }>>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [profileForm] = Form.useForm<Profile>()
  const [mealForm] = Form.useForm()
  const [targetForm] = Form.useForm()

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [savedProfile, savedMeals, savedTarget, savedAssessments] = await Promise.all([
        nutritionManagementApi.profile().catch(() => initialProfile), nutritionManagementApi.meals(),
        nutritionManagementApi.currentTarget().catch(() => null), nutritionManagementApi.assessments(),
      ])
      setProfile(savedProfile); profileForm.setFieldsValue(savedProfile); setMeals(savedMeals.items); setTarget(savedTarget); setAssessments(savedAssessments.items)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load nutrition management data.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  const saveProfile = async (values: Profile) => { try { const result = await nutritionManagementApi.saveProfile({ ...profile, ...values }); setProfile(result); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save profile.') } }
  const addMeal = async (values: Record<string, unknown>) => { try { await nutritionManagementApi.createMeal(values as Omit<Meal, 'id' | 'logged_at'>); mealForm.resetFields(); const response = await nutritionManagementApi.meals(); setMeals(response.items) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to add meal.') } }
  const calculate = async (values: Record<string, unknown>) => { try { setTarget(await nutritionManagementApi.calculateTarget(values)); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to calculate target.') } }
  const saveTarget = async () => { const inputs = targetForm.getFieldsValue(); try { setTarget(await nutritionManagementApi.saveTarget(inputs, new Date().toISOString().slice(0, 10))) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save target.') } }

  if (loading) return <Spin size="large" />
  return <div className="flex flex-col gap-4"><Title level={2}>Nutrition Management</Title>{error && <Alert message={error} type="error" showIcon closable onClose={() => setError('')} />}
    <Row gutter={[16, 16]}><Col xs={24} md={8}><Card><Statistic title="Meals logged" value={meals.length} /></Card></Col><Col xs={24} md={8}><Card><Statistic title="Daily calorie target" value={target?.recommended_calories ?? 'Not set'} suffix={target ? 'kcal' : ''} /></Card></Col><Col xs={24} md={8}><Card><Statistic title="Timezone" value={profile.timezone} valueStyle={{ fontSize: 18 }} /></Card></Col></Row>
    <Tabs items={[
      { key: 'profile', label: 'Profile', children: <Card title="Profile"><Form form={profileForm} layout="vertical" initialValues={profile} onFinish={saveProfile}><Row gutter={16}><Col span={12}><Form.Item name="timezone" label="Timezone" rules={[{ required: true }]}><Input /></Form.Item></Col><Col span={12}><Form.Item name="dietary_preference" label="Dietary preference"><Select options={['omnivore', 'vegetarian', 'vegan', 'pescatarian', 'other'].map(value => ({ value }))} /></Form.Item></Col><Col span={12}><Form.Item name="meals_per_day" label="Meals per day"><InputNumber min={1} max={10} className="w-full" /></Form.Item></Col><Col span={12}><Form.Item name="activity_level" label="Activity"><Select options={['sedentary', 'light', 'moderate', 'active', 'very_active'].map(value => ({ value }))} /></Form.Item></Col></Row><Button type="primary" htmlType="submit">Save profile</Button></Form></Card> },
      { key: 'meals', label: 'Meals', children: <Space direction="vertical" size="large" className="w-full"><Card title="Log a meal"><Form form={mealForm} layout="vertical" onFinish={addMeal}><Row gutter={16}><Col xs={24} md={6}><Form.Item name="meal_type" label="Meal type" rules={[{ required: true }]}><Select options={['breakfast', 'lunch', 'dinner', 'supper', 'snack'].map(value => ({ value }))} /></Form.Item></Col><Col xs={24} md={18}><Form.Item name="description" label="Description" rules={[{ required: true }]}><Input /></Form.Item></Col><Col span={6}><Form.Item name="calories" label="Calories"><InputNumber min={0} className="w-full" /></Form.Item></Col><Col span={6}><Form.Item name="protein_g" label="Protein (g)"><InputNumber min={0} className="w-full" /></Form.Item></Col><Col span={6}><Form.Item name="carbs_g" label="Carbs (g)"><InputNumber min={0} className="w-full" /></Form.Item></Col><Col span={6}><Form.Item name="fat_g" label="Fat (g)"><InputNumber min={0} className="w-full" /></Form.Item></Col></Row><Button type="primary" htmlType="submit">Add meal</Button></Form></Card><Card title="Meal history"><Table rowKey="id" dataSource={meals} pagination={{ pageSize: 10 }} columns={[{ title: 'Type', dataIndex: 'meal_type' }, { title: 'Description', dataIndex: 'description' }, { title: 'Calories', dataIndex: 'calories' }, { title: 'Logged', dataIndex: 'logged_at', render: value => new Date(value).toLocaleString() }]} /></Card></Space> },
      { key: 'targets', label: 'Targets', children: <Card title="Calculate targets"><Form form={targetForm} layout="vertical" onFinish={calculate}><Row gutter={16}>{[['age', 'Age'], ['weight_kg', 'Weight (kg)'], ['height_cm', 'Height (cm)']].map(([name, label]) => <Col xs={24} md={8} key={name}><Form.Item name={name} label={label} rules={[{ required: true }]}><InputNumber min={1} className="w-full" /></Form.Item></Col>)}<Col xs={24} md={8}><Form.Item name="gender" label="Gender" rules={[{ required: true }]}><Select options={['male', 'female', 'other'].map(value => ({ value }))} /></Form.Item></Col><Col xs={24} md={8}><Form.Item name="activity_level" label="Activity" rules={[{ required: true }]}><Select options={['sedentary', 'light', 'moderate', 'active', 'very_active'].map(value => ({ value }))} /></Form.Item></Col><Col xs={24} md={8}><Form.Item name="fitness_goal" label="Goal" rules={[{ required: true }]}><Select options={[{ value: 'weight_loss', label: 'Weight loss' }, { value: 'maintenance', label: 'Maintenance' }, { value: 'muscle_gain', label: 'Muscle gain' }]} /></Form.Item></Col></Row><Space><Button type="primary" htmlType="submit">Calculate</Button>{target && <Button onClick={() => void saveTarget()}>Save as revision</Button>}</Space></Form>{target && <Card size="small" className="mt-4"><Text strong>{target.recommended_calories} kcal/day</Text><div>Protein: {target.macro_targets.protein_g}g · Carbs: {target.macro_targets.carbs_g}g · Fat: {target.macro_targets.fat_g}g</div></Card>}</Card> },
      { key: 'foods', label: 'Foods', children: <Card title="Cache-only food lookup"><Input.Search placeholder="Search cached foods" onSearch={async value => { if (value.trim()) { try { setFoods((await nutritionManagementApi.foods(value)).items) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to search foods.') } } }} /><Table className="mt-4" rowKey="fdc_id" dataSource={foods} columns={[{ title: 'Food', dataIndex: 'name' }, { title: 'Calories', dataIndex: 'calories' }]} /></Card> },
      { key: 'assessments', label: 'Assessments', children: <Card title="Assessment history"><Table rowKey="id" dataSource={assessments} columns={[{ title: 'Status', dataIndex: 'status', render: value => <Tag>{value}</Tag> }, { title: 'Score', dataIndex: 'score' }, { title: 'Message', dataIndex: 'message' }, { title: 'Date', dataIndex: 'created_at', render: value => new Date(value).toLocaleString() }]} /></Card> },
    ]} />
  </div>
}

export default NutritionManagementPage