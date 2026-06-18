/**
 * Utility helpers for working with the unified model `capabilities` object
 * exposed by the backend Model response (Model.to_response_dict()).
 *
 * Falls back gracefully to legacy fields stored in `properties` when the
 * backend version hasn't been upgraded yet, so the UI never breaks.
 */

export type ModelCapabilityKey =
    | 'stream'
    | 'tools'
    | 'vision'
    | 'json_schema'
    | 'max_context_tokens'
    | 'max_output_tokens'
    | 'supported_response_formats';

export interface NormalizedCapabilities {
    stream: boolean;
    tools: boolean;
    vision: boolean;
    json_schema: boolean;
    max_context_tokens?: number;
    max_output_tokens?: number;
    supported_response_formats: string[];
}

const DEFAULT_FORMATS = ['text'];
const JSON_SCHEMA = 'json_schema';
const JSON_OBJECT = 'json_object';

/**
 * Enforce bidirectional consistency between `json_schema` (boolean capability)
 * and `supported_response_formats` (explicit format list).
 *
 * **Keep this logic in sync with**:
 *   - inference/app/models/capabilities_engine.py::normalize_capabilities
 *   - backend/app/models/model/capabilities_engine.py::normalize_capabilities
 *
 * Rules:
 *   1. If `supported_response_formats` contains `"json_schema"` but
 *      `json_schema` is false → set `json_schema = true`.
 *   2. If `json_schema = true` and `"json_schema"` is missing from
 *      `supported_response_formats` → append it.
 *   3. If `json_schema = true` and `supported_response_formats` is only
 *      `["text"]` → expand to `["text", "json_object", "json_schema"]`.
 */
export function normalizeCapabilities(caps: Partial<NormalizedCapabilities>): NormalizedCapabilities {
    const out: NormalizedCapabilities = {
        stream: Boolean(caps.stream),
        tools: Boolean(caps.tools),
        vision: Boolean(caps.vision),
        json_schema: Boolean(caps.json_schema),
        max_context_tokens: typeof caps.max_context_tokens === 'number' ? caps.max_context_tokens : undefined,
        max_output_tokens: typeof caps.max_output_tokens === 'number' ? caps.max_output_tokens : undefined,
        supported_response_formats:
            Array.isArray(caps.supported_response_formats) && caps.supported_response_formats.length
                ? [...caps.supported_response_formats]
                : [...DEFAULT_FORMATS],
    };

    // Rule 1: explicit formats win over boolean
    if (out.supported_response_formats.includes(JSON_SCHEMA) && !out.json_schema) {
        out.json_schema = true;
    }

    // Rule 2: boolean triggers format list extension
    if (out.json_schema && !out.supported_response_formats.includes(JSON_SCHEMA)) {
        out.supported_response_formats.push(JSON_SCHEMA);
    }

    // Rule 3: minimal list expansion
    if (out.json_schema && out.supported_response_formats.length === 1 && out.supported_response_formats[0] === 'text') {
        out.supported_response_formats = ['text', JSON_OBJECT, JSON_SCHEMA];
    }

    return out;
}

/**
 * Extract a normalized capabilities dict from any model-like object
 * (backend Model response, ModelSchema, or plain props object).
 */
export function getCapabilities(model: any): NormalizedCapabilities {
    if (!model) {
        return {
            stream: false,
            tools: false,
            vision: false,
            json_schema: false,
            supported_response_formats: [...DEFAULT_FORMATS],
        };
    }

    const caps: any = model.capabilities || {};
    const props: any = model.properties || model || {};

    const stream = Boolean(caps.stream ?? props.streaming);
    const tools = Boolean(caps.tools ?? props.function_call);
    const vision = Boolean(caps.vision ?? props.vision);
    const json_schema = Boolean(caps.json_schema ?? props.json_schema);

    const max_context_tokens =
        typeof caps.max_context_tokens === 'number'
            ? caps.max_context_tokens
            : typeof props.input_token_limit === 'number'
            ? props.input_token_limit
            : undefined;

    const max_output_tokens =
        typeof caps.max_output_tokens === 'number'
            ? caps.max_output_tokens
            : typeof props.output_token_limit === 'number'
            ? props.output_token_limit
            : undefined;

    let supported_response_formats: string[] = DEFAULT_FORMATS;
    if (Array.isArray(caps.supported_response_formats) && caps.supported_response_formats.length) {
        supported_response_formats = caps.supported_response_formats;
    } else if (Array.isArray(props.supported_response_formats) && props.supported_response_formats.length) {
        supported_response_formats = props.supported_response_formats;
    }

    return normalizeCapabilities({
        stream,
        tools,
        vision,
        json_schema,
        max_context_tokens,
        max_output_tokens,
        supported_response_formats,
    });
}

/**
 * Aggregate capabilities across multiple models (used in assistant
 * configuration where multiple chat models can be selected).
 *
 * For boolean capabilities we use AND — only when *every* model supports
 * it do we consider it safe to enable in the UI. Numeric fields take
 * the minimum (conservative). supported_response_formats is the
 * intersection.
 */
export function mergeCapabilities(models: any[] = []): NormalizedCapabilities {
    if (!models.length) {
        return {
            stream: false,
            tools: false,
            vision: false,
            json_schema: false,
            supported_response_formats: [...DEFAULT_FORMATS],
        };
    }
    const capsList = models.map((m) => getCapabilities(m));

    const stream = capsList.every((c) => c.stream);
    const tools = capsList.every((c) => c.tools);
    const vision = capsList.every((c) => c.vision);
    const json_schema = capsList.every((c) => c.json_schema);

    const max_context_tokens = capsList
        .map((c) => c.max_context_tokens)
        .filter((v): v is number => typeof v === 'number')
        .reduce((min, cur) => (cur < min ? cur : min), Infinity);
    const max_output_tokens = capsList
        .map((c) => c.max_output_tokens)
        .filter((v): v is number => typeof v === 'number')
        .reduce((min, cur) => (cur < min ? cur : min), Infinity);

    const intersection = capsList
        .map((c) => new Set(c.supported_response_formats))
        .reduce(
            (acc, cur) =>
                new Set([...acc].filter((x) => cur.has(x))),
            new Set(capsList[0].supported_response_formats),
        );

    return normalizeCapabilities({
        stream,
        tools,
        vision,
        json_schema,
        max_context_tokens: isFinite(max_context_tokens) ? max_context_tokens : undefined,
        max_output_tokens: isFinite(max_output_tokens) ? max_output_tokens : undefined,
        supported_response_formats: [...intersection],
    });
}

/** Returns a human-readable reason why a capability is not supported. */
export function capabilityUnsupportedReason(
    capability: ModelCapabilityKey,
    selectedCount: number = 0,
): string {
    const map: Record<ModelCapabilityKey, string> = {
        stream: 'streaming output (SSE)',
        tools: 'tool / function calling',
        vision: 'vision (image input)',
        json_schema: 'JSON schema / structured output',
        max_context_tokens: 'max context window',
        max_output_tokens: 'max output tokens',
        supported_response_formats: 'response format',
    };
    const base = map[capability] || capability;
    if (selectedCount > 1) {
        return `One or more of the selected models does not support ${base}. Enable this feature only when every selected model declares it.`;
    }
    return `The currently selected model does not support ${base}. Choose a model that declares this capability, or disable the feature.`;
}

/** Shorthand to quickly check a boolean capability. */
export function hasCapability(model: any, key: 'stream' | 'tools' | 'vision' | 'json_schema'): boolean {
    return getCapabilities(model)[key];
}
