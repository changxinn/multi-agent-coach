import { useEffect, useState } from 'react'
import { Table, Card, Typography, Tabs, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { api } from '@/lib/api'
import { ApiEndpoints, formatTableDateTime } from '@/lib/constants'

const { Title, Text } = Typography

interface RoutingRow {
  id: number
  user_id: number
  session_id?: string | null
  next_agent: string
  routing_reason?: string | null
  needs_clarification: boolean
  safety_flags: string[]
  user_message?: string | null
  created_at: string
}

interface SummaryRow {
  id: number
  user_id: number
  session_id?: string | null
  summary_type: string
  summary_text: string
  created_at: string
}

const routingColumns: ColumnsType<RoutingRow> = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: 'User', dataIndex: 'user_id', key: 'user_id', width: 80 },
  { title: 'Session', dataIndex: 'session_id', key: 'session_id', ellipsis: true },
  {
    title: 'Next agent',
    dataIndex: 'next_agent',
    key: 'next_agent',
    render: (value: string) => <Tag>{value}</Tag>,
  },
  { title: 'Reason', dataIndex: 'routing_reason', key: 'routing_reason', ellipsis: true },
  {
    title: 'Clarify',
    dataIndex: 'needs_clarification',
    key: 'needs_clarification',
    render: (value: boolean) => (value ? <Tag color="orange">yes</Tag> : <Tag>no</Tag>),
    width: 90,
  },
  {
    title: 'Safety flags',
    dataIndex: 'safety_flags',
    key: 'safety_flags',
    render: (flags: string[]) =>
      flags?.length ? flags.map((flag) => <Tag key={flag}>{flag}</Tag>) : '—',
  },
  { title: 'User message', dataIndex: 'user_message', key: 'user_message', ellipsis: true },
  {
    title: 'Created',
    dataIndex: 'created_at',
    key: 'created_at',
    render: (value: string) => formatTableDateTime(value),
  },
]

const summaryColumns: ColumnsType<SummaryRow> = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: 'User', dataIndex: 'user_id', key: 'user_id', width: 80 },
  {
    title: 'Type',
    dataIndex: 'summary_type',
    key: 'summary_type',
    render: (value: string) => <Tag color={value === 'daily' ? 'blue' : 'green'}>{value}</Tag>,
  },
  { title: 'Session', dataIndex: 'session_id', key: 'session_id', ellipsis: true },
  { title: 'Summary', dataIndex: 'summary_text', key: 'summary_text', ellipsis: true },
  {
    title: 'Created',
    dataIndex: 'created_at',
    key: 'created_at',
    render: (value: string) => formatTableDateTime(value),
  },
]

export function CoachDataPage() {
  const [routingRows, setRoutingRows] = useState<RoutingRow[]>([])
  const [summaryRows, setSummaryRows] = useState<SummaryRow[]>([])
  const [loadingRoutes, setLoadingRoutes] = useState(false)
  const [loadingSummaries, setLoadingSummaries] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoadingRoutes(true)
      setLoadingSummaries(true)
      try {
        const [routes, summaries] = await Promise.all([
          api.get<RoutingRow[]>(ApiEndpoints.Admin.HeadCoachRoutes),
          api.get<SummaryRow[]>(ApiEndpoints.Admin.Summaries),
        ])
        setRoutingRows(routes)
        setSummaryRows(summaries)
      } catch (err) {
        message.error(err instanceof Error ? err.message : 'Failed to load coach tables')
      } finally {
        setLoadingRoutes(false)
        setLoadingSummaries(false)
      }
    }
    void load()
  }, [])

  return (
    <div>
      <div className="mb-6">
        <Title level={2} className="mb-2">
          Head Coach & Summarizer
        </Title>
        <Text type="secondary">
          Routing decisions and saved summaries from your coaching agents
        </Text>
      </div>

      <Card>
        <Tabs
          items={[
            {
              key: 'routing',
              label: `Head Coach routes (${routingRows.length})`,
              children: (
                <Table
                  rowKey="id"
                  columns={routingColumns}
                  dataSource={routingRows}
                  loading={loadingRoutes}
                  pagination={{ pageSize: 8 }}
                  scroll={{ x: 1100 }}
                />
              ),
            },
            {
              key: 'summaries',
              label: `Summaries (${summaryRows.length})`,
              children: (
                <Table
                  rowKey="id"
                  columns={summaryColumns}
                  dataSource={summaryRows}
                  loading={loadingSummaries}
                  pagination={{ pageSize: 8 }}
                  scroll={{ x: 900 }}
                />
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}

export default CoachDataPage
