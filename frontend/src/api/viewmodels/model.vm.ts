export type ModelType = 'chat_completion' | 'text_embedding' | 'rerank' | 'wildcard';

export interface ModelProperties {
  function_call?: boolean;
  streaming?: boolean;
  input_token_limit?: number;
  output_token_limit?: number;
  embedding_size?: number;
  max_batch_size?: number;
  [key: string]: any;
}

export interface ModelDto {
  object: string;
  model_id: string;
  model_schema_id: string;
  provider_id: string;
  provider_model_id: string;
  name: string;
  type: ModelType;
  properties: ModelProperties;
  configs: Record<string, any>;
  display_credentials: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface ModelSchemaDto {
  model_schema_id: string;
  name: string;
  description: string;
  provider_id: string;
  provider_model_id?: string;
  type: ModelType;
  properties?: ModelProperties;
  allowed_configs: string[];
  config_schemas: any[];
  pricing?: Record<string, any>;
}

export interface ProviderDto {
  provider_id: string;
  name: string;
  description: string;
  credentials_schema: {
    type: string;
    properties: Record<string, { type: string; description: string; secret?: boolean }>;
    required: string[];
  };
  icon_svg_url: string;
  num_model_schemas: number;
  model_types: string[];
  resources: Record<string, string>;
  updated_timestamp: number;
}

export type ModelVM = ModelDto & {
  key: string;
  typeLabel: string;
  isChatCompletion: boolean;
  isTextEmbedding: boolean;
  isRerank: boolean;
  isWildcard: boolean;
  supportsFunctionCall: boolean;
  supportsStreaming: boolean;
  displayCredentials: Record<string, any>;
  createdAt: string;
  updatedAt: string;
};

export type ModelSchemaVM = ModelSchemaDto & {
  typeLabel: string;
};

export type ProviderVM = ProviderDto & {
  credentialsSchema: {
    properties: Record<string, { type: string; description: string; secret?: boolean }>;
    required: string[];
  };
  iconUrl: string;
  numModelSchemas: number;
  modelTypes: string[];
};

export interface ModelCreateRequest {
  name: string;
  model_schema_id: string;
  provider_model_id?: string;
  credentials: Record<string, any>;
  properties?: ModelProperties;
  type?: ModelType;
  host_type?: string;
}

export interface ModelUpdateRequest {
  name?: string;
  credentials?: Record<string, any>;
  properties?: ModelProperties;
  model_schema_id?: string;
  provider_model_id?: string;
  type?: ModelType;
  host_type?: string;
}
