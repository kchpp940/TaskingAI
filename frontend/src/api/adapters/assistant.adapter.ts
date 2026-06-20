import {
  AssistantDto,
  AssistantVM,
  AssistantMemoryDto,
  AssistantMemoryVM,
  RetrievalConfigDto,
  RetrievalConfigVM,
  RetrievalRefDto,
  RetrievalRefVM,
  ToolRefDto,
  ToolRefVM,
  MemoryType,
  RetrievalMethod,
  ToolType,
} from '../viewmodels';
import {
  formatDateTime,
  safeArray,
  safeNumber,
  safeObject,
  safeString,
  withTableKey,
} from './utils';

const MEMORY_TYPE_LABELS: Record<MemoryType, string> = {
  zero: 'Zero',
  naive: 'Naive',
  message_window: 'Message Window',
};

const RETRIEVAL_METHOD_LABELS: Record<RetrievalMethod, string> = {
  function_call: 'Function Call',
  user_message: 'User Message',
  memory: 'Memory',
};

const TOOL_TYPE_LABELS: Record<ToolType, string> = {
  action: 'Action',
  plugin: 'Plugin',
};

const getMemoryTypeLabel = (type: MemoryType): string => MEMORY_TYPE_LABELS[type] || type;
const getRetrievalMethodLabel = (method: RetrievalMethod): string => RETRIEVAL_METHOD_LABELS[method] || method;
const getToolTypeLabel = (type: ToolType): string => TOOL_TYPE_LABELS[type] || type;

export const adaptAssistantMemory = (dto: AssistantMemoryDto | undefined | null): AssistantMemoryVM => {
  const memory = safeObject(dto, { type: 'zero' as MemoryType });
  return {
    type: memory.type,
    typeLabel: getMemoryTypeLabel(memory.type),
    maxMessages: safeNumber(memory.max_messages, 0),
    maxTokens: safeNumber(memory.max_tokens, 0),
  };
};

export const adaptRetrievalConfig = (dto: RetrievalConfigDto | undefined | null): RetrievalConfigVM => {
  const config = safeObject(dto, { top_k: 3, method: 'user_message' as RetrievalMethod });
  return {
    topK: safeNumber(config.top_k, 3),
    maxTokens: safeNumber(config.max_tokens, 4096),
    scoreThreshold: config.score_threshold,
    method: config.method,
    methodLabel: getRetrievalMethodLabel(config.method),
    functionDescription: config.function_description,
  };
};

export const adaptRetrievalRef = (dto: RetrievalRefDto): RetrievalRefVM => {
  return {
    id: dto.id,
    collectionId: dto.id,
    name: safeString(dto.name, 'Untitled Collection'),
    type: dto.type,
  };
};

export const adaptRetrievalRefList = (dtos: RetrievalRefDto[]): RetrievalRefVM[] => {
  return safeArray(dtos, []).map(adaptRetrievalRef);
};

export const adaptToolRef = (dto: ToolRefDto): ToolRefVM => {
  return {
    id: dto.id,
    type: dto.type,
    name: safeString(dto.name),
    typeLabel: getToolTypeLabel(dto.type),
  };
};

export const adaptToolRefList = (dtos: ToolRefDto[]): ToolRefVM[] => {
  return safeArray(dtos, []).map(adaptToolRef);
};

export const adaptAssistant = (dto: AssistantDto): AssistantVM => {
  const memory = adaptAssistantMemory(dto.memory);
  const retrievalConfigs = adaptRetrievalConfig(dto.retrieval_configs);
  const tools = adaptToolRefList(dto.tools);
  const retrievals = adaptRetrievalRefList(dto.retrievals);
  const systemPromptTemplate = safeArray(dto.system_prompt_template, []);

  return {
    id: dto.assistant_id,
    key: dto.assistant_id,
    assistantId: dto.assistant_id,
    modelId: dto.model_id,
    modelName: safeString(dto.model_name, 'Unknown Model'),
    name: safeString(dto.name, 'Untitled Assistant'),
    description: safeString(dto.description),
    systemPromptTemplate,
    systemPromptText: systemPromptTemplate.join(' '),
    memory,
    tools,
    actionTools: tools.filter(t => t.type === 'action'),
    pluginTools: tools.filter(t => t.type === 'plugin'),
    retrievals,
    retrievalConfigs,
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptAssistantList = (dtos: AssistantDto[]): AssistantVM[] => {
  return dtos.map(adaptAssistant);
};

export const adaptAssistantForTable = (vm: AssistantVM): AssistantVM & { key: string } => withTableKey(vm);
