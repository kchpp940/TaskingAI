import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse } from '../client';
import {
  ChatDto,
  ChatVM,
  MessageDto,
  MessageVM,
  ChatCreateRequest,
  MessageCreateRequest,
  MessageGenerateRequest,
} from '../viewmodels';
import { adaptChat, adaptChatList, adaptMessage, adaptMessageList } from '../adapters';

const CHAT_BASE_URL = `${API_BASE_URL}`;

export interface ChatListParams {
  limit?: number;
  after?: string;
  order?: string;
}

export interface MessageListParams {
  limit?: number;
  after?: string;
  order?: string;
}

export const chatService = {
  async listChats(assistantId: string, params: ChatListParams = {}): Promise<PaginatedResponse<ChatVM>> {
    const query = buildListParams('', { limit: DEFAULT_LIMIT, ...params });
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<ChatDto>;
    return {
      data: adaptChatList(response.data),
      has_more: response.has_more,
    };
  },

  async getChat(assistantId: string, chatId: string): Promise<ChatVM> {
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}`;
    const response = await httpClient.get(url) as any as { data: ChatDto };
    return adaptChat(response.data);
  },

  async createChat(assistantId: string, params: ChatCreateRequest = {}): Promise<ChatVM> {
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats`;
    const response = await httpClient.post(url, params) as any as { data: ChatDto };
    return adaptChat(response.data);
  },

  async deleteChat(assistantId: string, chatId: string): Promise<void> {
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}`;
    await httpClient.delete(url);
  },

  async listMessages(
    assistantId: string,
    chatId: string,
    params: MessageListParams = {},
  ): Promise<PaginatedResponse<MessageVM>> {
    const query = buildListParams('', { limit: DEFAULT_LIMIT, ...params });
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}/messages${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<MessageDto>;
    return {
      data: adaptMessageList(response.data),
      has_more: response.has_more,
    };
  },

  async sendMessage(
    assistantId: string,
    chatId: string,
    params: MessageCreateRequest,
  ): Promise<MessageVM> {
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}/messages`;
    const response = await httpClient.post(url, params) as any as { data: MessageDto };
    return adaptMessage(response.data);
  },

  async generateMessage(
    assistantId: string,
    chatId: string,
    params: MessageGenerateRequest = {},
  ): Promise<MessageVM> {
    const url = `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}/generate`;
    const response = await httpClient.post(url, params) as any as { data: MessageDto };
    return adaptMessage(response.data);
  },

  getGenerateSseUrl(assistantId: string, chatId: string): string {
    return `${CHAT_BASE_URL}/assistants/${assistantId}/chats/${chatId}/generate`;
  },
};

export default chatService;
