import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  AssistantDto,
  AssistantVM,
  AssistantCreateRequest,
  AssistantUpdateRequest,
} from '../viewmodels';
import { adaptAssistant, adaptAssistantList } from '../adapters';

const ASSISTANT_BASE_URL = `${API_BASE_URL}`;

export interface AssistantListParams extends SearchParams {}

export const assistantService = {
  async list(params: AssistantListParams = {}): Promise<PaginatedResponse<AssistantVM>> {
    const query = buildListParams('assistant_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${ASSISTANT_BASE_URL}/ui/assistants${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<AssistantDto>;
    return {
      data: adaptAssistantList(response.data),
      has_more: response.has_more,
    };
  },

  async get(assistantId: string): Promise<AssistantVM> {
    const url = `${ASSISTANT_BASE_URL}/ui/assistants/${assistantId}`;
    const response = await httpClient.get(url) as any as { data: AssistantDto };
    return adaptAssistant(response.data);
  },

  async create(params: AssistantCreateRequest): Promise<AssistantVM> {
    const url = `${ASSISTANT_BASE_URL}/assistants`;
    const response = await httpClient.post(url, params) as any as { data: AssistantDto };
    return adaptAssistant(response.data);
  },

  async update(assistantId: string, params: AssistantUpdateRequest): Promise<AssistantVM> {
    const url = `${ASSISTANT_BASE_URL}/assistants/${assistantId}`;
    const response = await httpClient.post(url, params) as any as { data: AssistantDto };
    return adaptAssistant(response.data);
  },

  async delete(assistantId: string): Promise<void> {
    const url = `${ASSISTANT_BASE_URL}/assistants/${assistantId}`;
    await httpClient.delete(url);
  },
};

export default assistantService;
