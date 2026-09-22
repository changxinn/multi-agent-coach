import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Col, Form, Input, InputNumber, Row, Space, Typography, message } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { api } from '@/lib/api'

const { Title, Text } = Typography
const profileQueryKey = ['auth', 'profile'] as const

type FitnessProfile = {
  user_id: number
  fitness_goal: string
  fitness_level: string
  weight_kg: number | null
  height_cm: number | null
  age: number | null
}

type UserProfile = {
  id: number
  email: string
  name: string
  role: string
  fitness_profile: FitnessProfile
}

type ProfileFormValues = Pick<FitnessProfile, 'age' | 'weight_kg' | 'height_cm'>

export function MyProfilePage() {
  const queryClient = useQueryClient()
  const [form] = Form.useForm<ProfileFormValues>()
  const [messageApi, contextHolder] = message.useMessage()
  const profile = useQuery({
    queryKey: profileQueryKey,
    queryFn: () => api.get<UserProfile>('/auth/profile'),
  })
  const saveProfile = useMutation({
    mutationFn: (values: ProfileFormValues) => api.put<UserProfile>('/auth/profile', values),
    onSuccess: async (updatedProfile) => {
      queryClient.setQueryData(profileQueryKey, updatedProfile)
      await queryClient.invalidateQueries({ queryKey: ['nutrition'] })
      messageApi.success('Profile measurements saved.')
    },
    onError: (error: Error) => messageApi.error(error.message),
  })

  useEffect(() => {
    if (profile.data) {
      form.setFieldsValue(profile.data.fitness_profile)
    }
  }, [form, profile.data])

  return (
    <div className="flex flex-col gap-4">
      {contextHolder}
      <div>
        <Title level={2}><UserOutlined className="mr-2" />My Profile</Title>
        <Text type="secondary">Save your measurements for us to provide a holistic plan for you!</Text>
      </div>
      {profile.isError ? (
        <Alert type="error" showIcon title="Unable to load your profile" description={(profile.error as Error).message} />
      ) : (
        <Card loading={profile.isLoading} title="Account and measurements" style={{ maxWidth: 760 }}>
          <Form form={form} layout="vertical" onFinish={saveProfile.mutate} disabled={profile.isLoading}>
            <Row gutter={16}>
              <Col xs={24} md={12}><Form.Item label="Name"><Input value={profile.data?.name} readOnly /></Form.Item></Col>
              <Col xs={24} md={12}><Form.Item label="Email"><Input value={profile.data?.email} readOnly /></Form.Item></Col>
              <Col xs={24} md={8}><Form.Item name="age" label="Age (years)" rules={[{ required: true, message: 'Enter your age' }]}><InputNumber min={1} max={149} precision={0} style={{ width: '100%' }} /></Form.Item></Col>
              <Col xs={24} md={8}><Form.Item name="weight_kg" label="Weight (kg)" rules={[{ required: true, message: 'Enter your weight' }]}><InputNumber min={0.01} max={499.99} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
              <Col xs={24} md={8}><Form.Item name="height_cm" label="Height (cm)" rules={[{ required: true, message: 'Enter your height' }]}><InputNumber min={0.01} max={299.99} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
            </Row>
            <Space><Button type="primary" htmlType="submit" loading={saveProfile.isPending}>Save measurements</Button></Space>
          </Form>
        </Card>
      )}
    </div>
  )
}

export default MyProfilePage