import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  ActionDto,
  ActionVM,
  ActionBulkCreateRequest,
  ActionUpdateRequest,
} from '../viewmodels';
import { adaptAction, adaptActionList } from '../adapters';

const ACTION_BASE_URL = `${API_BASE_URL}`;

export interface ActionListParams extends SearchParams {}

export const actionService = {
  async list(params: ActionListParams = {}): Promise<PaginatedResponse<ActionVM>> {
    const query = buildListParams('action_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${ACTION_BASE_URL}/actions${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<ActionDto>;
    return {
      data: adaptActionList(response.data),
      has_more: response.has_more,
    };
  },

  async get(actionId: string): Promise<ActionVM> {
    const url = `${ACTION_BASE_URL}/actions/${actionId}`;
    const response = await httpClient.get(url) as any as { data: ActionDto };
    return adaptAction(response.data);
  },

  async bulkCreate(params: ActionBulkCreateRequest): Promise<ActionVM[]> {
    const url = `${ACTION_BASE_URL}/actions/bulk_create`;
    const response = await httpClient.post(url, params) as any as { data: ActionDto[] };
    return adaptActionList(response.data);
  },

  async update(actionId: string, params: ActionUpdateRequest): Promise<ActionVM> {
    const url = `${ACTION_BASE_URL}/actions/${actionId}`;
    const response = await httpClient.post(url, params) as any as { data: ActionDto };
    return adaptAction(response.data);
  },

  async delete(actionId: string): Promise<void> {
    const url = `${ACTION_BASE_URL}/actions/${actionId}`;
    await httpClient.delete(url);
  },
};

export default actionService;
