import {
  ChatDto,
  ChatVM,
  MessageDto,
  MessageVM,
  MessageRole,
  MessageGenerationLogDto,
  MessageGenerationLogVM,
} from '../viewmodels';
import { formatDateTime, safeNumber, safeString, withTableKey } from './utils';

const ROLE_LABELS: Record<MessageRole, string> = {
  user: 'User',
  assistant: 'Assistant',
};

const getRoleLabel = (role: MessageRole): string => ROLE_LABELS[role] || role;

const getStatusColor = (status?: 'start' | 'success' | 'error'): string => {
  switch (status) {
    case 'success':
      return 'green';
    case 'error':
      return 'red';
    case 'start':
      return 'orange';
    default:
      return 'gray';
  }
};

const formatEventLabel = (event: string): string => {
  if (!event) return '';
  return event
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const adaptChat = (dto: ChatDto): ChatVM => {
  return {
    id: dto.chat_id,
    key: dto.chat_id,
    chatId: dto.chat_id,
    assistantId: dto.assistant_id,
    name: dto.name,
    displayName: safeString(dto.name, 'New Chat'),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptChatList = (dtos: ChatDto[]): ChatVM[] => {
  return dtos.map(adaptChat);
};

export const adaptChatForList = (vm: ChatVM): ChatVM & { key: string } => withTableKey(vm);

export const adaptMessage = (dto: MessageDto): MessageVM => {
  return {
    id: dto.message_id,
    messageId: dto.message_id,
    chatId: dto.chat_id,
    assistantId: dto.assistant_id,
    role: dto.role,
    roleLabel: getRoleLabel(dto.role),
    isUser: dto.role === 'user',
    isAssistant: dto.role === 'assistant',
    content: safeString(dto.content?.text),
    numTokens: safeNumber(dto.num_tokens, 0),
    createdAt: formatDateTime(dto.created_timestamp),
    createdTimestamp: dto.created_timestamp,
  };
};

export const adaptMessageList = (dtos: MessageDto[]): MessageVM[] => {
  return dtos.map(adaptMessage);
};

export const adaptMessageGenerationLog = (
  dto: MessageGenerationLogDto,
): MessageGenerationLogVM => {
  return {
    event: dto.event,
    eventLabel: formatEventLabel(dto.event),
    eventId: dto.event_id,
    eventStep: dto.event_step,
    timestamp: dto.timestamp,
    content: dto.content || {},
    status: dto.status,
    statusColor: getStatusColor(dto.status),
    durationMs: dto.duration_ms,
  };
};

export const adaptMessageGenerationLogList = (
  dtos: MessageGenerationLogDto[],
): MessageGenerationLogVM[] => {
  return dtos.map(adaptMessageGenerationLog);
};
