export type MessageRole = 'user' | 'assistant';

export interface MessageContentDto {
  text: string;
}

export interface ChatDto {
  object: string;
  assistant_id: string;
  chat_id: string;
  name: string;
  metadata: Record<string, any>;
  memory: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface MessageDto {
  object: string;
  assistant_id: string;
  chat_id: string;
  message_id: string;
  role: MessageRole;
  content: MessageContentDto;
  num_tokens: number;
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface MessageGenerationLogDto {
  object: 'MessageGenerationLog';
  session_id: string;
  event: string;
  event_id: string;
  event_step: string;
  timestamp: number;
  content: Record<string, any>;
  status?: 'start' | 'success' | 'error';
  duration_ms?: number;
  input_summary?: string;
  error?: Record<string, any>;
}

export interface MessageChunkDto {
  object: 'MessageChunk';
  delta: string;
}

export interface ChatVM {
  id: string;
  key: string;
  chatId: string;
  assistantId: string;
  name: string;
  displayName: string;
  createdAt: string;
  updatedAt: string;
  createdTimestamp: number;
  updatedTimestamp: number;
}

export interface MessageVM {
  id: string;
  messageId: string;
  chatId: string;
  assistantId: string;
  role: MessageRole;
  roleLabel: string;
  isUser: boolean;
  isAssistant: boolean;
  content: string;
  numTokens: number;
  createdAt: string;
  createdTimestamp: number;
}

export interface MessageGenerationLogVM {
  event: string;
  eventLabel: string;
  eventId: string;
  eventStep: string;
  timestamp: number;
  content: Record<string, any>;
  status?: 'start' | 'success' | 'error';
  statusColor: string;
  durationMs?: number;
}

export interface ChatCreateRequest {
  name?: string;
  metadata?: Record<string, any>;
}

export interface MessageCreateRequest {
  role: MessageRole;
  content: MessageContentDto;
}

export interface MessageGenerateRequest {
  system_prompt_variables?: Record<string, any>;
  stream?: boolean;
  debug?: boolean;
}
