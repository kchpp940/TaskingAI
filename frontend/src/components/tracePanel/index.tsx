import { useState } from 'react'
import { Collapse, Tag, Tooltip } from 'antd'
import { CheckCircleFilled, CloseCircleFilled, ClockCircleFilled, LoadingOutlined, RightOutlined } from '@ant-design/icons'
import styles from './tracePanel.module.scss'

interface TraceEvent {
    object?: string
    trace_id?: string
    event_id?: string
    event_type?: string
    status?: string | null
    timestamp?: number
    duration_ms?: number | null
    content?: Record<string, any>
    error?: string | null
}

interface TracePanelProps {
    events: TraceEvent[]
    visible: boolean
    onClear?: () => void
}

const EVENT_LABELS: Record<string, string> = {
    memory_build: 'Memory Build',
    system_prompt_build: 'System Prompt',
    retrieval: 'Retrieval',
    tool_call: 'Tool Call',
    chat_completion: 'Chat Completion',
    inference: 'Inference',
    usage_summary: 'Usage Summary',
}

const EVENT_COLORS: Record<string, string> = {
    memory_build: '#722ed1',
    system_prompt_build: '#13c2c2',
    retrieval: '#1890ff',
    tool_call: '#fa8c16',
    chat_completion: '#52c41a',
    inference: '#52c41a',
    usage_summary: '#595959',
}

const STATUS_LABELS: Record<string, string> = {
    started: 'Start',
    completed: 'End',
    error: 'Error',
}

function formatDuration(ms: number | null | undefined): string {
    if (ms == null) return '-'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
}

function getStatusIcon(status: string | null | undefined, isLastEvent: boolean) {
    if (status === 'error') return <CloseCircleFilled style={{ color: '#ff4d4f' }} />
    if (status === 'completed') return <CheckCircleFilled style={{ color: '#52c41a' }} />
    if (status === 'started') return isLastEvent ? <LoadingOutlined style={{ color: '#1890ff' }} /> : <ClockCircleFilled style={{ color: '#faad14' }} />
    return <ClockCircleFilled style={{ color: '#d9d9d9' }} />
}

function getContentSummary(event: TraceEvent): string {
    if (!event.content) return ''
    const c = event.content
    const et = event.event_type || ''

    switch (et) {
        case 'memory_build':
            return `${c.num_messages ?? 0} messages loaded`
        case 'system_prompt_build':
            return `${c.prompt_length ?? 0} chars${c.has_retrieval ? ' + retrieval' : ''}`
        case 'retrieval':
            if (event.status === 'started') return `query: "${(c.query_text ?? '').slice(0, 60)}${(c.query_text ?? '').length > 60 ? '...' : ''}" | top_k: ${c.top_k ?? '-'}`
            if (event.status === 'completed') return `${c.result_count ?? c.results?.length ?? 0} results returned`
            return ''
        case 'tool_call':
            if (event.status === 'started') return `${c.name ?? c.tool_type ?? 'tool'}: ${c.tool_id ?? ''}`
            if (event.status === 'completed') return `${c.tool_type ?? 'tool'} completed`
            return ''
        case 'chat_completion':
        case 'inference':
            if (event.status === 'started') return `model: ${c.provider_model_id ?? c.model_id ?? '-'} | ${c.message_count ?? '-'} msgs | ${c.function_count ?? '-'} fns`
            if (event.status === 'completed') return `in: ${c.input_tokens ?? 0} / out: ${c.output_tokens ?? 0} tokens${c.has_function_calls ? ' + function_calls' : ''}`
            return ''
        case 'usage_summary':
            return `total in: ${c.total_input_tokens ?? 0} / out: ${c.total_output_tokens ?? 0} tokens`
        default:
            return ''
    }
}

function groupEventsByEventId(events: TraceEvent[]): TraceEvent[][] {
    const groups: Record<string, TraceEvent[]> = {}
    const orderedIds: string[] = []
    for (const e of events) {
        const key = e.event_id || e.timestamp?.toString() || Math.random().toString()
        if (!groups[key]) {
            groups[key] = []
            orderedIds.push(key)
        }
        groups[key].push(e)
    }
    return orderedIds.map(id => groups[id])
}

export default function TracePanel({ events, visible, onClear }: TracePanelProps) {
    const [expandedIds, setExpandedIds] = useState<string[]>([])

    if (!visible || events.length === 0) return null

    const traceEvents = events.filter(e => e.object === 'TraceEvent')
    if (traceEvents.length === 0) return null

    const grouped = groupEventsByEventId(traceEvents)

    const collapseItems = grouped.map((group, idx) => {
        const first = group[0]
        const last = group[group.length - 1]
        const eventKey = first.event_id || `trace-${idx}`
        const eventLabel = EVENT_LABELS[first.event_type || ''] || first.event_type || 'Unknown'
        const eventColor = EVENT_COLORS[first.event_type || ''] || '#8c8c8c'
        const status = last.status || first.status || ''
        const duration = last.duration_ms || first.duration_ms
        const errorMsg = last.error || first.error
        const isLastGroup = idx === grouped.length - 1

        const label = (
            <div className={styles.traceLabel}>
                <span className={styles.traceIcon}>{getStatusIcon(status, isLastGroup)}</span>
                <Tag color={eventColor} className={styles.eventTag}>{eventLabel}</Tag>
                <span className={styles.traceStep}>{STATUS_LABELS[first.status || ''] || first.status || ''}</span>
                {duration != null && <span className={styles.traceDuration}>{formatDuration(duration)}</span>}
                {errorMsg && <span className={styles.traceError}>{errorMsg.slice(0, 50)}</span>}
                {!errorMsg && <span className={styles.traceSummary}>{getContentSummary(status === 'completed' ? last : first)}</span>}
            </div>
        )

        const detailContent = group.map((e, i) => (
            <div key={i} className={styles.detailSection}>
                <div className={styles.detailHeader}>
                    <span className={styles.detailStep}>{STATUS_LABELS[e.status || ''] || e.status || ''}</span>
                    {e.duration_ms != null && <span className={styles.detailDuration}>{formatDuration(e.duration_ms)}</span>}
                    {e.status && <Tag color={e.status === 'error' ? 'red' : e.status === 'completed' ? 'green' : 'blue'} className={styles.statusTag}>{e.status}</Tag>}
                </div>
                {e.error && <div className={styles.detailError}>{e.error}</div>}
                <pre className={styles.detailContent}>{JSON.stringify(e.content, null, 2)}</pre>
                {e.timestamp && <div className={styles.detailTimestamp}>ts: {e.timestamp}</div>}
            </div>
        ))

        return {
            key: eventKey,
            label,
            children: <div className={styles.detailWrapper}>{detailContent}</div>,
        }
    })

    return (
        <div className={styles.tracePanel}>
            <div className={styles.traceHeader}>
                <span className={styles.traceTitle}>Generation Trace</span>
                <div className={styles.traceHeaderRight}>
                    <span className={styles.traceCount}>{traceEvents.length} events</span>
                    {onClear && <button className={styles.clearBtn} onClick={onClear}>Clear</button>}
                </div>
            </div>
            <Collapse
                activeKey={expandedIds}
                onChange={(keys) => setExpandedIds(keys as string[])}
                expandIcon={({ isActive }) => <RightOutlined rotate={isActive ? 90 : 0} className={styles.expandIcon} />}
                items={collapseItems}
                className={styles.traceCollapse}
                size="small"
            />
        </div>
    )
}
