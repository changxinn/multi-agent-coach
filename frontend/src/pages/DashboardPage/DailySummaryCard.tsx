import { useEffect, useState } from 'react'
import { Button, Card, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { api } from '@/lib/api'
import { ApiEndpoints } from '@/lib/constants'
import { quoteOfTheDay } from '@/lib/daily-quote'

const { Paragraph, Text } = Typography

function stripGlanceHeading(text: string): string {
  return text.replace(/^(your day at a glance:?\s*)+/i, '').trim()
}

const LABEL_COLORS: Record<string, string> = {
  'recovery emphasis': '#0f766e',
  fuel: '#c2410c',
}

function withLabelHighlights(text: string) {
  const parts = text.split(/\b(Recovery emphasis|Fuel)\b/gi)
  return parts.map((part, index) => {
    const color = LABEL_COLORS[part.toLowerCase()]
    if (!color) {
      return part
    }
    return (
      <strong key={`${part}-${index}`} style={{ color, fontWeight: 700 }}>
        {part}
      </strong>
    )
  })
}

interface DailySummaryResponse {
  summary: string
  generated_at: string
  reused: boolean
}

export function DailySummaryCard() {
  const [summary, setSummary] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const quote = quoteOfTheDay()

  const loadSummary = async (forceNew = false) => {
    setLoading(true)
    setError(null)
    try {
      const path = forceNew
        ? `${ApiEndpoints.Chat.DailySummary}?refresh=1`
        : ApiEndpoints.Chat.DailySummary
      const data = await api.post<DailySummaryResponse>(path, {})
      setSummary(stripGlanceHeading(data.summary))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load daily summary')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Fetch the initial server-backed summary on mount.
    void loadSummary()
  }, [])

  return (
    <Card
      title="Your day at a glance"
      extra={
        <Button
          type="link"
          icon={<ReloadOutlined />}
          onClick={() => void loadSummary(true)}
          loading={loading}
        >
          Refresh
        </Button>
      }
    >
      {error && <Text type="danger">{error}</Text>}
      {!error && (
        <>
          <Paragraph
            italic
            style={{ color: '#8c8c8c', marginBottom: 12, marginTop: 0 }}
          >
            {quote}
          </Paragraph>
          <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {loading && !summary
              ? "Preparing today's briefing…"
              : withLabelHighlights(summary)}
          </Paragraph>
        </>
      )}
    </Card>
  )
}
