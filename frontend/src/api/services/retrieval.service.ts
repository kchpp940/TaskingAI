import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  CollectionDto,
  CollectionVM,
  CollectionCreateRequest,
  CollectionUpdateRequest,
} from '../viewmodels';
import { adaptCollection, adaptCollectionList } from '../adapters';

const COLLECTION_BASE_URL = `${API_BASE_URL}`;

export interface CollectionListParams extends SearchParams {}

export const collectionService = {
  async list(params: CollectionListParams = {}): Promise<PaginatedResponse<CollectionVM>> {
    const query = buildListParams('collection_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${COLLECTION_BASE_URL}/ui/collections${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<CollectionDto>;
    return {
      data: adaptCollectionList(response.data),
      has_more: response.has_more,
    };
  },

  async get(collectionId: string): Promise<CollectionVM> {
    const url = `${COLLECTION_BASE_URL}/collections/${collectionId}`;
    const response = await httpClient.get(url) as any as { data: CollectionDto };
    return adaptCollection(response.data);
  },

  async create(params: CollectionCreateRequest): Promise<CollectionVM> {
    const url = `${COLLECTION_BASE_URL}/collections`;
    const response = await httpClient.post(url, params) as any as { data: CollectionDto };
    return adaptCollection(response.data);
  },

  async update(collectionId: string, params: CollectionUpdateRequest): Promise<CollectionVM> {
    const url = `${COLLECTION_BASE_URL}/collections/${collectionId}`;
    const response = await httpClient.post(url, params) as any as { data: CollectionDto };
    return adaptCollection(response.data);
  },

  async delete(collectionId: string): Promise<void> {
    const url = `${COLLECTION_BASE_URL}/collections/${collectionId}`;
    await httpClient.delete(url);
  },
};

export default collectionService;
