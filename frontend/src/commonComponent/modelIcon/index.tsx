import DimensionIcon from '@/assets/img/dimsionIcon.svg?react'
import FunctionCall from '@/assets/img/functionCallIcon.svg?react'
import InputTokenIcon from '@/assets/img/inputTokenIcon.svg?react'
import MaxBatchSizeIcon from '@/assets/img/maxBatchSizeIcon.svg?react'
import OutputTokenIcon from '@/assets/img/outputTokensIcon.svg?react'
import StreamIcon from '@/assets/img/streamIcon.svg?react'
import VisionInputIcon from '@/assets/img/visionInputIcon.svg?react'
import Dollar from '@/assets/img/dollar.svg?react'
import styles from './modelIcon.module.scss'
import {
    getCapabilities as standardizeCapabilities,
    NormalizedCapabilities,
} from '@/utils/capabilities'

/**
 * Normalize either legacy `properties` or the new unified `capabilities`
 * object into a single display dict for the ModelIcon component.
 *
 * Delegates the heavy lifting — including bidirectional consistency between
 * `json_schema` and `supported_response_formats` — to the canonical
 * `utils/capabilities.ts` implementation, then renames fields to the legacy
 * display keys that ModelIcon already knows.
 */
function normalizeCapabilities(props: any): Record<string, any> {
    if (!props) return {}
    const caps: NormalizedCapabilities = standardizeCapabilities(props)
    const out: Record<string, any> = {}

    if (caps.stream) out.streaming = true
    if (caps.tools) out.function_call = true
    if (caps.vision) out.vision = true
    if (caps.json_schema) out.json_schema = true
    if (caps.max_context_tokens) out.max_context_tokens = caps.max_context_tokens
    if (caps.max_output_tokens) out.output_token_limit = caps.max_output_tokens
    if (Array.isArray(caps.supported_response_formats) && caps.supported_response_formats.length > 1) {
        out.supported_response_formats = caps.supported_response_formats
    }

    // text-embedding only fields (legacy properties, not part of capabilities)
    const rawProps = props.properties || props || {}
    if (rawProps.embedding_size) out.embedding_size = rawProps.embedding_size
    if (rawProps.max_batch_size) out.max_batch_size = rawProps.max_batch_size

    return out
}

function ModelIcon(props: any) {
    const { isShowText = true } = props
    const merged = normalizeCapabilities(props)

    const IconReverse: Record<string, React.ReactNode> = {
        'embedding_size': <DimensionIcon />,
        'function_call': <FunctionCall />,
        'max_context_tokens': <InputTokenIcon />,
        'max_batch_size': <MaxBatchSizeIcon />,
        'output_token_limit': <OutputTokenIcon />,
        'streaming': <StreamIcon />,
        'vision': <VisionInputIcon />,
        'json_schema': <Dollar />,
        'supported_response_formats': <Dollar />,
    }

    const textReverse: Record<string, string> = {
        'embedding_size': 'embedding size',
        'function_call': 'function call',
        'max_context_tokens': 'context tokens',
        'max_batch_size': 'max batch size',
        'output_token_limit': 'output tokens limit',
        'streaming': 'stream',
        'vision': 'vision input',
        'json_schema': 'JSON schema',
        'supported_response_formats': 'response formats',
    }

    const renderEntries = Object.entries(merged).filter(([, value]) => {
        if (Array.isArray(value)) return value.length > 0
        if (typeof value === 'boolean') return value
        return value !== undefined && value !== null && value !== ''
    })

    return (
        <div className={styles['model-icon']}>
            {renderEntries.map(([key, value]) => {
                if (key === 'supported_response_formats' && Array.isArray(value)) {
                    // Render as a single capability summarizing the supported formats
                    const usefulFormats = (value as string[]).filter((f) => f !== 'text')
                    if (usefulFormats.length === 0) return null
                    return (
                        <div
                            key={key}
                            className={`${styles.modelIcon} ${!isShowText && styles.modelIconText}`}
                            title={`Supported response formats: ${(value as string[]).join(', ')}`}
                        >
                            <Dollar />
                            {isShowText && (
                                <>
                                    <span className={styles.name}>response formats</span>
                                    <span className={styles.value}>:&nbsp;&nbsp;{usefulFormats.join(', ')}</span>
                                </>
                            )}
                        </div>
                    )
                }
                return (
                    <div
                        key={key}
                        className={`${styles.modelIcon} ${!isShowText && styles.modelIconText}`}
                    >
                        {IconReverse[key as keyof typeof IconReverse]}
                        {isShowText && (
                            <>
                                <span className={styles.name}>
                                    {textReverse[key as keyof typeof textReverse] || key}
                                </span>
                                {typeof value !== 'boolean' && value && (
                                    <span className={styles.value}>:&nbsp;&nbsp;{value as string | number}</span>
                                )}
                            </>
                        )}
                    </div>
                )
            })}
        </div>
    )
}
export default ModelIcon
