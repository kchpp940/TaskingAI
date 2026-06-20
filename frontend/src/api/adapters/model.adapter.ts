import {
  ModelDto,
  ModelVM,
  ModelSchemaDto,
  ModelSchemaVM,
  ProviderDto,
  ProviderVM,
  ModelType,
  ModelProperties,
} from '../viewmodels';
import { formatDateTime, safeObject, safeString, safeNumber, withTableKey } from './utils';

const MODEL_TYPE_LABELS: Record<ModelType, string> = {
  chat_completion: 'Chat Completion',
  text_embedding: 'Text Embedding',
  rerank: 'Rerank',
  wildcard: 'Wildcard',
};

const getModelTypeLabel = (type: ModelType): string => MODEL_TYPE_LABELS[type] || type;

export const adaptModel = (dto: ModelDto): ModelVM => {
  const properties: ModelProperties = safeObject(dto.properties, {});
  const vm: ModelVM = {
    id: dto.model_id,
    key: dto.model_id,
    modelId: dto.model_id,
    modelSchemaId: dto.model_schema_id,
    providerId: dto.provider_id,
    providerModelId: safeString(dto.provider_model_id),
    name: safeString(dto.name, 'Untitled Model'),
    type: dto.type,
    typeLabel: getModelTypeLabel(dto.type),
    isChatCompletion: dto.type === 'chat_completion',
    isTextEmbedding: dto.type === 'text_embedding',
    isRerank: dto.type === 'rerank',
    isWildcard: dto.type === 'wildcard',
    properties,
    supportsFunctionCall: safeNumber(properties.function_call ? 1 : 0, 0) === 1 || !!properties.function_call,
    supportsStreaming: safeNumber(properties.streaming ? 1 : 0, 0) === 1 || !!properties.streaming,
    configs: safeObject(dto.configs, {}),
    displayCredentials: safeObject(dto.display_credentials, {}),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
  return vm;
};

export const adaptModelList = (dtos: ModelDto[]): ModelVM[] => {
  return dtos.map(adaptModel);
};

export const adaptModelSchema = (dto: ModelSchemaDto): ModelSchemaVM => {
  return {
    id: dto.model_schema_id,
    modelSchemaId: dto.model_schema_id,
    name: safeString(dto.name),
    description: safeString(dto.description),
    providerId: dto.provider_id,
    providerModelId: dto.provider_model_id,
    type: dto.type,
    typeLabel: getModelTypeLabel(dto.type),
    properties: safeObject(dto.properties, {}),
    allowedConfigs: dto.allowed_configs || [],
    configSchemas: dto.config_schemas || [],
  };
};

export const adaptModelSchemaList = (dtos: ModelSchemaDto[]): ModelSchemaVM[] => {
  return dtos.map(adaptModelSchema);
};

export const adaptProvider = (dto: ProviderDto): ProviderVM => {
  const credentialsSchema = safeObject(dto.credentials_schema, { properties: {}, required: [] });
  return {
    id: dto.provider_id,
    providerId: dto.provider_id,
    name: safeString(dto.name),
    description: safeString(dto.description),
    credentialsSchema: {
      properties: safeObject(credentialsSchema.properties, {}),
      required: Array.isArray(credentialsSchema.required) ? credentialsSchema.required : [],
    },
    iconUrl: safeString(dto.icon_svg_url),
    numModelSchemas: safeNumber(dto.num_model_schemas, 0),
    modelTypes: dto.model_types || [],
  };
};

export const adaptProviderList = (dtos: ProviderDto[]): ProviderVM[] => {
  return dtos.map(adaptProvider);
};

export const adaptModelForTable = (vm: ModelVM): ModelVM & { key: string } => withTableKey(vm);
