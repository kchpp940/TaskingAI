import DimensionIcon from '@/assets/img/dimsionIcon.svg?react'
import FunctionCall from '@/assets/img/functionCallIcon.svg?react'
import InputTokenIcon from '@/assets/img/inputTokenIcon.svg?react'
import MaxBatchSizeIcon from '@/assets/img/maxBatchSizeIcon.svg?react'
import OutputTokenIcon from '@/assets/img/outputTokensIcon.svg?react'
import StreamIcon from '@/assets/img/streamIcon.svg?react'
import VisionInputIcon from '@/assets/img/visionInputIcon.svg?react'
import Dollar from '@/assets/img/dollar.svg?react'
import styles from './modelIcon.module.scss'

/**
 * Normalize either legacy `properties` or the new unified `capabilities`
 * object into a single display dict for the ModelIcon component.
 */
function normalizeCapabilities(props: any): Record<string, any> {
    if (!props) return {}
    const capabilities = props.capabilities || {}
    const properties = props.properties || props
    const out: Record<string, any> = {}

    // --- new unified capabilities ---
    if (capabilities.stream) out.streaming = true
    if (capabilities.tools) out.function_call = true
    if (capabilities.vision) out.vision = true
    if (capabilities.json_schema) out.json_schema = true
    if (capabilities.max_context_tokens) out.max_context_tokens = capabilities.max_context_tokens
    if (capabilities.max_output_tokens) out.output_token_limit = capabilities.max_output_tokens
    if (Array.isArray(capabilities.supported_response_formats)) {
        out.supported_response_formats = capabilities.supported_response_formats
    }

    // --- fallback to legacy properties (only when missing above) ---
    if (out.streaming === undefined && properties.streaming) out.streaming = true
    if (out.function_call === undefined && properties.function_call) out.function_call = true
    if (out.vision === undefined && properties.vision) out.vision = true
    if (out.json_schema === undefined && properties.json_schema) out.json_schema = true
    if (out.max_context_tokens === undefined && properties.input_token_limit) {
        out.max_context_tokens = properties.input_token_limit
    }
    if (out.output_token_limit === undefined && properties.output_token_limit) {
        out.output_token_limit = properties.output_token_limit
    }
    if (out.supported_response_formats === undefined && Array.isArray(properties.supported_response_formats)) {
        out.supported_response_formats = properties.supported_response_formats
    }

    // text-embedding only fields
    if (properties.embedding_size) out.embedding_size = properties.embedding_size
    if (properties.max_batch_size) out.max_batch_size = properties.max_batch_size

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
