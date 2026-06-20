import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  ApikeyDto,
  ApikeyVM,
  ApikeyCreateRequest,
  ApikeyUpdateRequest,
} from '../viewmodels';
import { adaptApikey, adaptApikeyList } from '../adapters';

const APIKEY_BASE_URL = `${API_BASE_URL}`;

export interface ApikeyListParams extends SearchParams {}

export const apikeyService = {
  async list(params: ApikeyListParams = {}): Promise<PaginatedResponse<ApikeyVM>> {
    const query = buildListParams('apikey_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${APIKEY_BASE_URL}/apikeys${query ? `?${query}` : ''}`;
    const response = await httpClient.get<PaginatedResponse<ApikeyDto>>(url);
    return {
      data: adaptApikeyList(response.data),
      has_more: response.has_more,
    };
  },

  async get(apikeyId: string, plain: string = 'false'): Promise<ApikeyVM> {
    const url = `${APIKEY_BASE_URL}/apikeys/${apikeyId}?plain=${plain}`;
    const response = await httpClient.get<{ data: ApikeyDto }>(url);
    return adaptApikey(response.data);
  },

  async create(params: ApikeyCreateRequest): Promise<ApikeyVM> {
    const url = `${APIKEY_BASE_URL}/apikeys`;
    const response = await httpClient.post<{ data: ApikeyDto }>(url, params);
    return adaptApikey(response.data);
  },

  async update(apikeyId: string, params: ApikeyUpdateRequest): Promise<ApikeyVM> {
    const url = `${APIKEY_BASE_URL}/apikeys/${apikeyId}`;
    const response = await httpClient.post<{ data: ApikeyDto }>(url, params);
    return adaptApikey(response.data);
  },

  async delete(apikeyId: string): Promise<void> {
    const url = `${APIKEY_BASE_URL}/apikeys/${apikeyId}`;
    await httpClient.delete(url);
  },
};

export default apikeyService;
