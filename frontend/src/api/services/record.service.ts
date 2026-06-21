import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  RecordDto,
  RecordVM,
  RecordCreateRequest,
  RecordUpdateRequest,
} from '../viewmodels';
import { adaptRecord, adaptRecordList } from '../adapters';

const RECORD_BASE_URL = `${API_BASE_URL}`;

export interface RecordListParams extends SearchParams {}

export const recordService = {
  async list(collectionId: string, params: RecordListParams = {}): Promise<PaginatedResponse<RecordVM>> {
    const query = buildListParams('record_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${RECORD_BASE_URL}/collections/${collectionId}/records${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<RecordDto>;
    return {
      data: adaptRecordList(response.data),
      has_more: response.has_more,
    };
  },

  async get(collectionId: string, recordId: string): Promise<RecordVM> {
    const url = `${RECORD_BASE_URL}/collections/${collectionId}/records/${recordId}`;
    const response = await httpClient.get(url) as any as { data: RecordDto };
    return adaptRecord(response.data);
  },

  async create(collectionId: string, params: RecordCreateRequest): Promise<RecordVM> {
    const url = `${RECORD_BASE_URL}/collections/${collectionId}/records`;
    const response = await httpClient.post(url, params) as any as { data: RecordDto };
    return adaptRecord(response.data);
  },

  async update(collectionId: string, recordId: string, params: RecordUpdateRequest): Promise<RecordVM> {
    const url = `${RECORD_BASE_URL}/collections/${collectionId}/records/${recordId}`;
    const response = await httpClient.post(url, params) as any as { data: RecordDto };
    return adaptRecord(response.data);
  },

  async delete(collectionId: string, recordId: string): Promise<void> {
    const url = `${RECORD_BASE_URL}/collections/${collectionId}/records/${recordId}`;
    await httpClient.delete(url);
  },

  async uploadFile(params: FormData): Promise<{ file_id: string }> {
    const url = `${RECORD_BASE_URL}/files`;
    const response = await httpClient.post(url, params) as any as { data: { file_id: string } };
    return response.data;
  },
};

export default recordService;
