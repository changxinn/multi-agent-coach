import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Col, Descriptions, Divider, Form, Input, InputNumber, Modal, Pagination, Row, Select, Space, Table, Tag, Timeline, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { api } from '@/lib/api'
import { formatTableDateTime } from '@/lib/constants'
import {
  allergenStatuses,
  compatibilityReviewsApi,
  compatibilityReviewStatuses,
  reviewDecisions,
  strictSuitabilityKeys,
  type AllergenStatus,
  type CompatibilityReviewDetail,
  type CompatibilityReviewHistoryItem,
  type CompatibilityReviewStatus,
  type ReviewDecision,
  type ReviewQueueItem,
  type ReviewSubmission,
  type StrictSuitabilityKey,
  type StrictSuitabilityValue,
} from '@/lib/compatibilityReviews'

const { Title, Text } = Typography
const pageSize = 25

const suitabilityLabels: Record<StrictSuitabilityKey, string> = {
  vegetarian: 'Vegetarian', vegan: 'Vegan', pescatarian: 'Pescatarian', halal: 'Halal', kosher: 'Kosher',
  gluten_free: 'Gluten-free', dairy_free: 'Dairy-free', egg_free: 'Egg-free', soy_free: 'Soy-free',
  nut_free: 'Nut-free', no_pork: 'No pork', no_beef: 'No beef', alcohol_free: 'Alcohol-free',
}
const commonAllergenOptions = [
  'milk', 'egg', 'peanut', 'tree_nuts', 'soy', 'wheat', 'fish', 'shellfish', 'sesame',
].map((value) => ({ value, label: value.replaceAll('_', ' ') }))

type AuthProfile = { is_nutrition_compatibility_admin: boolean }
type ReviewFormValues = Omit<ReviewSubmission, 'food_cache_id' | 'evidence'> & { evidence_source?: string }

function statusTag(status: string) {
  const color = status === 'approved' ? 'green' : status === 'rejected' ? 'red' : status === 'review_required' ? 'gold' : 'blue'
  return <Tag color={color}>{status.replaceAll('_', ' ')}</Tag>
}

function selectedSuitability(detail: CompatibilityReviewDetail | undefined) {
  return strictSuitabilityKeys.reduce<Partial<Record<StrictSuitabilityKey, StrictSuitabilityValue>>>((values, key) => {
    const value = detail?.strict_suitability?.[key]
    if (value === 'suitable' || value === 'unsuitable') values[key] = value
    return values
  }, {})
}

function allSuitabilityValues(value: StrictSuitabilityValue) {
  return strictSuitabilityKeys.reduce<Partial<Record<StrictSuitabilityKey, StrictSuitabilityValue>>>((values, key) => {
    values[key] = value
    return values
  }, {})
}

function ReviewWorkspace({ foodCacheId }: { foodCacheId: number }) {
  const queryClient = useQueryClient()
  const [form] = Form.useForm<ReviewFormValues>()
  const [messageApi, contextHolder] = message.useMessage()
  const [saveFeedback, setSaveFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const reviewDecisionRef = useRef<HTMLDivElement>(null)
  const [reviewDecisionHeight, setReviewDecisionHeight] = useState<number>()
  const [isWideLayout, setIsWideLayout] = useState(() => window.matchMedia('(min-width: 992px)').matches)
  const detail = useQuery({ queryKey: ['compatibility-reviews', 'detail', foodCacheId], queryFn: () => compatibilityReviewsApi.getDetail(foodCacheId) })
  const history = useQuery({ queryKey: ['compatibility-reviews', 'history', foodCacheId], queryFn: () => compatibilityReviewsApi.getHistory(foodCacheId) })
  const decision = Form.useWatch('review_status', form)

  useEffect(() => {
    if (!detail.data) return
    const evidenceSource = typeof detail.data.evidence?.source === 'string' ? detail.data.evidence.source : ''
    form.setFieldsValue({
      review_status: reviewDecisions.includes(detail.data.review_status as ReviewDecision) ? detail.data.review_status as ReviewDecision : 'review_required',
      allergen_status: allergenStatuses.includes(detail.data.allergen_status as AllergenStatus) ? detail.data.allergen_status as AllergenStatus : 'unknown',
      known_allergens: detail.data.known_allergens ?? [],
      strict_suitability: selectedSuitability(detail.data),
      evidence_source: evidenceSource,
      confidence: detail.data.confidence,
      classifier_version: detail.data.classifier_version,
      policy_version: detail.data.policy_version ?? 'compatibility_review_v1',
      review_note: detail.data.review_note,
    })
  }, [detail.data, form])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 992px)')
    const updateLayout = () => setIsWideLayout(mediaQuery.matches)
    updateLayout()
    mediaQuery.addEventListener('change', updateLayout)
    return () => mediaQuery.removeEventListener('change', updateLayout)
  }, [])

  useEffect(() => {
    const element = reviewDecisionRef.current
    if (!element) return
    const updateHeight = () => setReviewDecisionHeight(element.getBoundingClientRect().height)
    updateHeight()
    const observer = new ResizeObserver(updateHeight)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const saveReview = useMutation({
    mutationFn: (payload: ReviewSubmission) => compatibilityReviewsApi.submit(payload),
    onSuccess: async () => {
      const successMessage = 'Compatibility decision saved and added to the audit history.'
      setSaveFeedback({ type: 'success', message: successMessage })
      messageApi.success(successMessage)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['compatibility-reviews', 'queue'] }),
        queryClient.invalidateQueries({ queryKey: ['compatibility-reviews', 'detail', foodCacheId] }),
        queryClient.invalidateQueries({ queryKey: ['compatibility-reviews', 'history', foodCacheId] }),
      ])
    },
    onError: (error: Error) => {
      setSaveFeedback({ type: 'error', message: error.message })
      messageApi.error(error.message)
    },
  })

  const submit = (values: ReviewFormValues) => {
    setSaveFeedback(null)
    const strictSuitability = values.strict_suitability ?? {}
    if (values.review_status === 'approved') {
      const missing = strictSuitabilityKeys.filter((key) => !strictSuitability[key])
      if (values.allergen_status !== 'known') {
        form.setFields([{ name: 'allergen_status', errors: ['Approved foods require known allergen metadata.'] }])
        form.scrollToField('allergen_status', { block: 'center', focus: true })
        return
      }
      if (!values.evidence_source?.trim()) {
        form.setFields([{ name: 'evidence_source', errors: ['Approved foods require evidence.'] }])
        form.scrollToField('evidence_source', { block: 'center', focus: true })
        return
      }
      if (values.confidence == null) {
        form.setFields([{ name: 'confidence', errors: ['Approved foods require confidence.'] }])
        form.scrollToField('confidence', { block: 'center', focus: true })
        return
      }
      if (missing.length > 0) {
        form.setFields(missing.map((key) => ({ name: ['strict_suitability', key], errors: ['Required for approval.'] })))
        form.scrollToField(['strict_suitability', missing[0]], { block: 'center', focus: true })
        return
      }
    }
    saveReview.mutate({
      food_cache_id: foodCacheId,
      review_status: values.review_status,
      allergen_status: values.allergen_status,
      known_allergens: values.known_allergens ?? [],
      strict_suitability: strictSuitability,
      evidence: values.evidence_source?.trim() ? { source: values.evidence_source.trim() } : {},
      confidence: values.confidence ?? null,
      classifier_version: values.classifier_version?.trim() || null,
      policy_version: values.policy_version.trim(),
      review_note: values.review_note?.trim() || null,
    })
  }

  if (detail.isError) return <Alert type="error" showIcon title="Unable to load compatibility review" description={(detail.error as Error).message} />
  const record = detail.data
  const metadataCardHeight = isWideLayout ? reviewDecisionHeight : undefined
  return <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
    {contextHolder}
    <Card loading={detail.isLoading} title="Food compatibility record">
      {record && <Descriptions column={{ xs: 1, sm: 2 }} size="small" items={[
        { key: 'food', label: 'Food', children: record.description },
        { key: 'provider', label: 'Provider', children: `${record.provider} / ${record.provider_food_id}` },
        { key: 'status', label: 'Review status', children: statusTag(record.review_status) },
        { key: 'allergens', label: 'Allergen status', children: record.allergen_status },
        { key: 'reviewer', label: 'Last reviewer', children: record.reviewer_email ?? 'Not reviewed' },
        { key: 'reviewed', label: 'Reviewed', children: record.reviewed_at ? formatTableDateTime(record.reviewed_at) : 'Not reviewed' },
      ]} />}
    </Card>
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={14}>
        <div ref={reviewDecisionRef}><Card title="Review decision" loading={detail.isLoading}>
          <Alert type="info" showIcon title="Reviewer identity is recorded from your authenticated session." description="Do not include reviewer identity in review data; the server supplies it." style={{ marginBottom: 16 }} />
          {saveFeedback && <Alert type={saveFeedback.type} showIcon title={saveFeedback.message} closable onClose={() => setSaveFeedback(null)} style={{ marginBottom: 16 }} />}
          <Form form={form} layout="vertical" onFinish={submit} disabled={detail.isLoading}>
            <Row gutter={16}>
              <Col xs={24} md={12}><Form.Item name="review_status" label="Decision" rules={[{ required: true }]}><Select options={reviewDecisions.map((value) => ({ value, label: value.replaceAll('_', ' ') }))} /></Form.Item></Col>
              <Col xs={24} md={12}><Form.Item name="allergen_status" label="Allergen metadata" rules={[{ required: true }]}><Select options={allergenStatuses.map((value) => ({ value, label: value }))} /></Form.Item></Col>
            </Row>
            <Form.Item name="known_allergens" label="Known allergens" extra="Select a common allergen or type a normalized allergen name."><Select mode="tags" options={commonAllergenOptions} placeholder="For example: milk protein" /></Form.Item>
            <Row gutter={16}>
              <Col xs={24} md={12}><Form.Item name="evidence_source" label="Evidence" extra="Required for approved decisions."><Input placeholder="For example: manufacturer label" /></Form.Item></Col>
              <Col xs={24} md={6}><Form.Item name="confidence" label="Confidence (0–1)" extra="Required for approved decisions."><InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} /></Form.Item></Col>
              <Col xs={24} md={6}><Form.Item name="policy_version" label="Policy version" rules={[{ required: true, message: 'Enter the policy version.' }]}><Input /></Form.Item></Col>
            </Row>
            <Form.Item name="classifier_version" label="Classifier version"><Input placeholder="Optional" /></Form.Item>
            <Divider orientation="left">Strict suitability <Space size="small"><Button size="small" onClick={() => form.setFieldValue('strict_suitability', allSuitabilityValues('suitable'))}>Set all as suitable</Button><Button size="small" onClick={() => form.setFieldValue('strict_suitability', allSuitabilityValues('unsuitable'))}>Set all as unsuitable</Button></Space></Divider>
            {decision === 'approved' && <Alert type="warning" showIcon title="Every suitability decision is required for approval." style={{ marginBottom: 16 }} />}
            <Row gutter={16}>{strictSuitabilityKeys.map((key) => (
              <Col xs={24} sm={12} key={key}><Form.Item name={['strict_suitability', key]} label={suitabilityLabels[key]}><Select allowClear options={[{ value: 'suitable', label: 'Suitable' }, { value: 'unsuitable', label: 'Unsuitable' }]} /></Form.Item></Col>
            ))}</Row>
            <Form.Item name="review_note" label="Review note"><Input.TextArea rows={3} maxLength={4000} showCount /></Form.Item>
            <Button type="primary" htmlType="submit" loading={saveReview.isPending}>{saveReview.isPending ? 'Saving review…' : 'Save review decision'}</Button>
          </Form>
        </Card></div>
      </Col>
      <Col xs={24} lg={10} style={{ display: 'flex' }}>
        <Card title="Current metadata" loading={detail.isLoading} style={{ display: 'flex', flex: 1, flexDirection: 'column', height: metadataCardHeight, maxHeight: metadataCardHeight, overflow: 'hidden' }} styles={{ body: { display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0, overflow: 'hidden' } }}>
          {record && <div style={{ display: 'flex', flex: 1, flexDirection: 'column', gap: 16, minHeight: 0, overflow: 'hidden' }}>
            <div><Text strong>Known allergens</Text><br />{record.known_allergens?.length ? record.known_allergens.map((item) => <Tag key={item}>{item}</Tag>) : <Text type="secondary">None recorded</Text>}</div>
            <div><Text strong>Evidence</Text><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.evidence, null, 2)}</pre></div>
            <div style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0 }}><Text strong>Source metadata</Text><pre style={{ flex: 1, margin: 0, minHeight: 0, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.raw_response, null, 2)}</pre></div>
          </div>}
        </Card>
      </Col>
    </Row>
    <Card title="Read-only audit history" loading={history.isLoading}>
      {history.isError ? <Alert type="error" showIcon title="Unable to load history" description={(history.error as Error).message} /> : (
        <Timeline items={(history.data?.items ?? []).map((item: CompatibilityReviewHistoryItem) => ({
          color: item.result_review_status === 'approved' ? 'green' : item.result_review_status === 'rejected' ? 'red' : 'blue',
          children: <div><Space wrap><Text strong>{item.prior_review_status ?? 'No prior status'} → {item.result_review_status}</Text>{statusTag(item.result_review_status)}</Space><br /><Text type="secondary">{item.reviewer_email} · {formatTableDateTime(item.reviewed_at)}</Text>{item.review_note && <><br /><Text>{item.review_note}</Text></>}<pre style={{ maxHeight: 140, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(item.metadata_snapshot, null, 2)}</pre></div>,
        }))} />
      )}
      {!history.isLoading && (history.data?.items.length ?? 0) === 0 && <Text type="secondary">No review decisions have been recorded yet.</Text>}
    </Card>
  </Space>
}

export function CompatibilityReviewsPage() {
  const [statuses, setStatuses] = useState<CompatibilityReviewStatus[]>([...compatibilityReviewStatuses])
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const profile = useQuery({ queryKey: ['auth', 'profile'], queryFn: () => api.get<AuthProfile>('/auth/profile') })
  const queue = useQuery({
    queryKey: ['compatibility-reviews', 'queue', statuses, query, offset],
    queryFn: () => compatibilityReviewsApi.getQueue({ statuses, query, offset, limit: pageSize }),
    enabled: profile.data?.is_nutrition_compatibility_admin === true,
  })
  const columns = useMemo<ColumnsType<ReviewQueueItem>>(() => [
    { title: 'Food', dataIndex: 'description', ellipsis: true, width: '45%' },
    { title: 'Status', dataIndex: 'review_status', render: statusTag },
    { title: 'Updated', dataIndex: 'updated_at', render: (value: string) => formatTableDateTime(value) },
    { title: 'Action', render: (_, item) => <Button onClick={() => setSelectedId(item.food_cache_id)}>Review</Button> },
  ], [])

  if (profile.isLoading) return <Card loading />
  if (profile.isError) return <Alert type="error" showIcon title="Unable to verify reviewer access" description={(profile.error as Error).message} />
  if (!profile.data?.is_nutrition_compatibility_admin) return <Alert type="error" showIcon title="Compatibility reviewer access required" description="You do not have permission to access compatibility reviews. The server also enforces this authorization." />

  const items = queue.data?.items ?? []
  const total = queue.data?.total ?? 0
  const currentPage = Math.floor(offset / pageSize) + 1
  return <div className="flex flex-col gap-4">
    <div><Title level={2}><SafetyCertificateOutlined className="mr-2" />Compatibility Reviews</Title><Text type="secondary">Review food compatibility evidence and record auditable safety decisions.</Text></div>
    <Card title="Review queue" extra={<Button icon={<ReloadOutlined />} onClick={() => queue.refetch()} loading={queue.isFetching}>Refresh</Button>}>
      <Form layout="vertical"><Row gutter={16}><Col xs={24} md={12}><Form.Item label="Search food name"><Input allowClear value={query} placeholder="Search food descriptions" onChange={(event) => { setQuery(event.target.value); setOffset(0) }} /></Form.Item></Col><Col xs={24} md={12}><Form.Item label="Queue statuses"><Select mode="multiple" value={statuses} options={compatibilityReviewStatuses.map((value) => ({ value, label: value.replaceAll('_', ' ') }))} onChange={(next) => { setStatuses(next); setOffset(0) }} /></Form.Item></Col></Row></Form>
      {queue.isError ? <Alert type="error" showIcon title="Unable to load the review queue" description={(queue.error as Error).message} /> : <Table rowKey="food_cache_id" loading={queue.isLoading} dataSource={items} columns={columns} scroll={{ x: 850 }} pagination={false} locale={{ emptyText: 'No foods match the selected review statuses.' }} />}
      <Pagination style={{ marginTop: 16 }} current={currentPage} pageSize={pageSize} total={total} showSizeChanger={false} disabled={queue.isFetching} onChange={(page) => setOffset((page - 1) * pageSize)} showTotal={(recordTotal, range) => `${range[0]}–${range[1]} of ${recordTotal} records`} />
    </Card>
    <Modal title="Compatibility review" open={selectedId !== null} onCancel={() => setSelectedId(null)} footer={null} width={1200} destroyOnHidden styles={{ body: { maxHeight: '75vh', overflowY: 'auto', paddingRight: 8 } }}>
      {selectedId !== null && <ReviewWorkspace foodCacheId={selectedId} />}
    </Modal>
  </div>
}