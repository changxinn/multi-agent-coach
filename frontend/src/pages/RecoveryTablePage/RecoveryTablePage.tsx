import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tabs, Typography, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api } from '@/lib/api'

const { Title, Text } = Typography
type Kind = 'sleep-logs' | 'check-ins' | 'assessments'
type RecordData = {
  id: number; user_id: number; created_at: string
  duration_minutes?: number; quality?: number; notes?: string | null
  energy?: number; soreness?: number; stress?: number
  status?: string; score?: number; response?: Record<string, unknown>; tool_trace?: string[]
}
type FormData = Omit<RecordData, 'id' | 'created_at' | 'response' | 'tool_trace'> & {
  response?: string; tool_trace?: string
}
const labels: Record<Kind, string> = {
  'sleep-logs': 'Sleep logs', 'check-ins': 'Recovery check-ins', assessments: 'Recovery assessments',
}
const numericFields: Record<Kind, { name: string; label: string; min: number; max: number }[]> = {
  'sleep-logs': [
    { name: 'duration_minutes', label: 'Sleep duration (minutes)', min: 0, max: 1440 },
    { name: 'quality', label: 'Sleep quality (1–5)', min: 1, max: 5 },
  ],
  'check-ins': [
    { name: 'energy', label: 'Energy (1–10)', min: 1, max: 10 },
    { name: 'soreness', label: 'Soreness (1–10)', min: 1, max: 10 },
    { name: 'stress', label: 'Stress (1–10)', min: 1, max: 10 },
  ],
  assessments: [{ name: 'score', label: 'Score', min: 0, max: 2147483647 }],
}

function RecoveryTable({ kind }: { kind: Kind }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [userId, setUserId] = useState<number | null>(null)
  const [editing, setEditing] = useState<RecordData | null>(null)
  const [open, setOpen] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [form] = Form.useForm<FormData>()
  const [messageApi, contextHolder] = message.useMessage()
  const endpoint = `/recovery/${kind}`
  const query = useQuery({
    queryKey: ['recovery', kind, page, pageSize, userId],
    queryFn: () => api.get<{ items: RecordData[]; total: number }>(
      `${endpoint}?page=${page}&page_size=${pageSize}${userId ? `&user_id=${userId}` : ''}`),
  })
  const save = useMutation({
    mutationFn: (values: FormData) => {
      const payload = kind === 'assessments'
        ? { ...values, response: JSON.parse(values.response || '{}'), tool_trace: JSON.parse(values.tool_trace || '[]') }
        : values
      return editing ? api.put(`${endpoint}/${editing.id}`, payload) : api.post(endpoint, payload)
    },
    onSuccess: async () => {
      setOpen(false)
      messageApi.success(editing ? 'Record updated' : 'Record created')
      await queryClient.invalidateQueries({ queryKey: ['recovery', kind] })
    },
    onError: (error: Error) => setSaveError(error.message),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`${endpoint}/${id}`),
    onSuccess: async () => {
      messageApi.success('Record deleted')
      if (query.data?.items.length === 1 && page > 1) setPage(page - 1)
      await queryClient.invalidateQueries({ queryKey: ['recovery', kind] })
    },
    onError: (error: Error) => messageApi.error(error.message),
  })
  const showEditor = (record: RecordData | null) => {
    setEditing(record)
    setSaveError(null)
    form.resetFields()
    if (record) {
      const { id: _id, created_at: _createdAt, response, tool_trace, ...values } = record
      form.setFieldsValue(kind === 'assessments'
        ? { ...values, response: JSON.stringify(response, null, 2), tool_trace: JSON.stringify(tool_trace, null, 2) }
        : values)
    } else if (userId) form.setFieldValue('user_id', userId)
    setOpen(true)
  }
  const columns: ColumnsType<RecordData> = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: 'User ID', dataIndex: 'user_id', width: 100 },
    ...numericFields[kind].map(field => ({ title: field.label, dataIndex: field.name })),
    ...(kind === 'assessments' ? [{ title: 'Status', dataIndex: 'status' }] : [{ title: 'Notes', dataIndex: 'notes', ellipsis: true }]),
    { title: 'Created', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: 'Actions', key: 'actions', render: (_, record) => <Space>
      <Button onClick={() => showEditor(record)}>Edit</Button>
      <Popconfirm title="Delete this recovery record?" description="This permanently removes the record." onConfirm={() => remove.mutateAsync(record.id).catch(() => undefined)}>
        <Button danger loading={remove.isPending && remove.variables === record.id} disabled={remove.isPending}>Delete</Button>
      </Popconfirm>
    </Space> },
  ]
  return <>
    {contextHolder}
    <Space wrap style={{ marginBottom: 16 }}>
      <Text>Filter by user ID</Text>
      <InputNumber aria-label="Filter by user ID" min={1} precision={0} value={userId} onChange={value => { setUserId(value); setPage(1) }} />
      <Button onClick={() => { setUserId(null); setPage(1) }}>Clear</Button>
      <Button icon={<ReloadOutlined />} onClick={() => query.refetch()} loading={query.isFetching}>Refresh</Button>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => showEditor(null)}>Add record</Button>
    </Space>
    {query.isError && <Alert type="error" showIcon title="Could not load recovery records" description={query.error.message} style={{ marginBottom: 16 }} />}
    <Table<RecordData> rowKey="id" columns={columns} dataSource={query.data?.items || []} loading={query.isFetching}
      scroll={{ x: 900 }}
      locale={{ emptyText: query.isError ? 'Unable to load records. Try Refresh.' : 'No recovery records yet. Add a record to get started.' }}
      pagination={{ current: page, pageSize, total: query.data?.total || 0, showSizeChanger: true,
        showTotal: total => `${total} records`, onChange: (next, size) => { setPage(size !== pageSize ? 1 : next); setPageSize(size) } }}
      expandable={kind === 'assessments' ? { expandedRowRender: record => <>
        <Text strong>Response</Text><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.response, null, 2)}</pre>
        <Text strong>Tool trace</Text><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.tool_trace, null, 2)}</pre>
      </> } : undefined}
    />
    <Modal title={`${editing ? 'Edit' : 'Add'} ${labels[kind].toLowerCase()} record`} open={open}
      onCancel={() => { if (!save.isPending) setOpen(false) }} onOk={() => form.submit()} confirmLoading={save.isPending}
      cancelButtonProps={{ disabled: save.isPending }} okText="Save" forceRender>
      {saveError && <Alert type="error" showIcon title={saveError} style={{ marginBottom: 16 }} />}
      <Form form={form} layout="vertical" onFinish={values => { setSaveError(null); save.mutate(values) }} disabled={save.isPending}>
        <Form.Item name="user_id" label="User ID" extra="Enter the ID of an existing user." rules={[{ required: true, message: 'Enter a user ID' }]}>
          <InputNumber min={1} max={2147483647} precision={0} style={{ width: '100%' }} />
        </Form.Item>
        {numericFields[kind].map(field => <Form.Item key={field.name} name={field.name} label={field.label} rules={[{ required: true, message: `Enter ${field.label.toLowerCase()}` }]}>
          <InputNumber min={field.min} max={field.max} precision={0} style={{ width: '100%' }} />
        </Form.Item>)}
        {kind === 'assessments' ? <>
          <Form.Item name="status" label="Status" rules={[{ required: true }]}><Select options={['green', 'amber', 'red', 'escalate'].map(value => ({ value, label: value }))} /></Form.Item>
          {(['response', 'tool_trace'] as const).map(name => <Form.Item key={name} name={name} label={name === 'response' ? 'Response (JSON object)' : 'Tool trace (JSON array of strings)'} rules={[{ required: true }, {
            validator: async (_, value: string) => {
              try {
                const parsed = JSON.parse(value)
                if (name === 'response' ? !parsed || typeof parsed !== 'object' || Array.isArray(parsed) : !Array.isArray(parsed) || parsed.some(item => typeof item !== 'string')) throw new Error()
              } catch { throw new Error(name === 'response' ? 'Enter a valid JSON object' : 'Enter a JSON array of strings') }
            },
          }]}><Input.TextArea rows={5} /></Form.Item>)}
        </> : <Form.Item name="notes" label="Notes"><Input.TextArea rows={3} maxLength={1000} showCount /></Form.Item>}
      </Form>
    </Modal>
  </>
}

export function RecoveryTablePage() {
  const [kind, setKind] = useState<Kind>('sleep-logs')
  return <div>
    <Title level={2}>Recovery Table</Title>
    <Text type="secondary">Manage sleep logs, recovery check-ins, and assessments.</Text>
    <Card style={{ marginTop: 24 }}>
      <Tabs activeKey={kind} onChange={value => setKind(value as Kind)} items={Object.entries(labels).map(([key, label]) => ({ key, label }))} />
      <RecoveryTable key={kind} kind={kind} />
    </Card>
  </div>
}

export default RecoveryTablePage
