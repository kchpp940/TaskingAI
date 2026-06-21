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
import { formatDateTime, safeObject, safeString, safeNumber } from './utils';

const MODEL_TYPE_LABELS: Record<ModelType, string> = {
  chat_completion: 'Chat Completion',
  text_embedding: 'Text Embedding',
  rerank: 'Rerank',
  wildcard: 'Wildcard',
};

const getModelTypeLabel = (type: ModelType): string => MODEL_TYPE_LABELS[type] || type;

export const adaptModel = (dto: ModelDto): ModelVM => {
  const properties: ModelProperties = safeObject(dto.properties, {});
  return {
    id: dto.model_id,
    modelSchemaId: dto.model_schema_id,
    providerId: dto.provider_id,
    providerModelId: dto.provider_model_id,
    name: dto.name,
    type: dto.type,
    properties: properties,
    configs: dto.configs,
    displayCredentials: safeObject(dto.display_credentials, {}),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
    key: dto.model_id,
    typeLabel: getModelTypeLabel(dto.type),
    isChatCompletion: dto.type === 'chat_completion',
    isTextEmbedding: dto.type === 'text_embedding',
    isRerank: dto.type === 'rerank',
    isWildcard: dto.type === 'wildcard',
    supportsFunctionCall: safeNumber(properties.function_call ? 1 : 0, 0) === 1 || !!properties.function_call,
    supportsStreaming: safeNumber(properties.streaming ? 1 : 0, 0) === 1 || !!properties.streaming,
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
  };
};

export const adaptModelList = (dtos: ModelDto[]): ModelVM[] => {
  return dtos.map(adaptModel);
};

export const adaptModelSchema = (dto: ModelSchemaDto): ModelSchemaVM => {
  return {
    modelSchemaId: dto.model_schema_id,
    name: dto.name,
    description: dto.description,
    providerId: dto.provider_id,
    providerModelId: dto.provider_model_id,
    type: dto.type,
    properties: dto.properties,
    allowedConfigs: dto.allowed_configs,
    configSchemas: dto.config_schemas,
    pricing: dto.pricing,
    typeLabel: getModelTypeLabel(dto.type),
  };
};

export const adaptModelSchemaList = (dtos: ModelSchemaDto[]): ModelSchemaVM[] => {
  return dtos.map(adaptModelSchema);
};

export const adaptProvider = (dto: ProviderDto): ProviderVM => {
  const credentialsSchema = safeObject(dto.credentials_schema, { type: '', properties: {}, required: [] });
  return {
    providerId: dto.provider_id,
    name: dto.name,
    description: dto.description,
    credentialsSchema: {
      type: credentialsSchema.type || '',
      properties: safeObject(credentialsSchema.properties, {}),
      required: Array.isArray(credentialsSchema.required) ? credentialsSchema.required : [],
    },
    iconUrl: safeString(dto.icon_svg_url),
    numModelSchemas: safeNumber(dto.num_model_schemas, 0),
    modelTypes: dto.model_types || [],
    resources: dto.resources,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptProviderList = (dtos: ProviderDto[]): ProviderVM[] => {
  return dtos.map(adaptProvider);
};
