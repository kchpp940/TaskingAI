export type MemoryType = 'zero' | 'naive' | 'message_window';
export type RetrievalMethod = 'function_call' | 'user_message' | 'memory';
export type ToolType = 'action' | 'plugin';

export interface AssistantMemoryDto {
  type: MemoryType;
  max_messages?: number;
  max_tokens?: number;
}

export interface RetrievalRefDto {
  type: 'collection';
  id: string;
  name?: string;
}

export interface ToolRefDto {
  type: ToolType;
  id: string;
  name?: string;
}

export interface RetrievalConfigDto {
  top_k: number;
  max_tokens?: number;
  score_threshold?: number;
  method: RetrievalMethod;
  function_description?: string;
}

export interface AssistantDto {
  object: string;
  assistant_id: string;
  model_id: string;
  model_name?: string;
  name: string;
  description: string;
  system_prompt_template: string[];
  memory: AssistantMemoryDto;
  tools: ToolRefDto[];
  retrievals: RetrievalRefDto[];
  retrieval_configs: RetrievalConfigDto;
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface AssistantMemoryVM {
  type: MemoryType;
  typeLabel: string;
  maxMessages: number;
  maxTokens: number;
}

export interface RetrievalConfigVM {
  topK: number;
  maxTokens: number;
  scoreThreshold?: number;
  method: RetrievalMethod;
  methodLabel: string;
  functionDescription?: string;
}

export interface RetrievalRefVM {
  id: string;
  collectionId: string;
  name: string;
  type: 'collection';
}

export interface ToolRefVM {
  id: string;
  type: ToolType;
  name: string;
  typeLabel: string;
}

export interface AssistantVM {
  id: string;
  key: string;
  assistantId: string;
  modelId: string;
  modelName: string;
  name: string;
  description: string;
  systemPromptTemplate: string[];
  systemPromptText: string;
  memory: AssistantMemoryVM;
  tools: ToolRefVM[];
  actionTools: ToolRefVM[];
  pluginTools: ToolRefVM[];
  retrievals: RetrievalRefVM[];
  retrievalConfigs: RetrievalConfigVM;
  createdAt: string;
  updatedAt: string;
  createdTimestamp: number;
  updatedTimestamp: number;
}

export interface AssistantCreateRequest {
  model_id: string;
  name?: string;
  description?: string;
  system_prompt_template?: string[];
  memory?: AssistantMemoryDto;
  tools?: ToolRefDto[];
  retrievals?: RetrievalRefDto[];
  retrieval_configs?: RetrievalConfigDto;
}

export interface AssistantUpdateRequest extends Partial<AssistantCreateRequest> {}
