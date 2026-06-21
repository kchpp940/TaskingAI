import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  ModelDto,
  ModelVM,
  ModelSchemaDto,
  ModelSchemaVM,
  ProviderDto,
  ProviderVM,
  ModelType,
  ModelCreateRequest,
  ModelUpdateRequest,
} from '../viewmodels';
import { adaptModel, adaptModelList, adaptModelSchema, adaptProviderList } from '../adapters';

const MODEL_BASE_URL = `${API_BASE_URL}`;

export interface ModelListParams extends SearchParams {
  type?: ModelType;
}

export const modelService = {
  async list(params: ModelListParams = {}): Promise<PaginatedResponse<ModelVM>> {
    const query = buildListParams('model_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${MODEL_BASE_URL}/models${query ? `?${query}` : ''}`;
    const response = await httpClient.get(url) as any as PaginatedResponse<ModelDto>;
    return {
      data: adaptModelList(response.data),
      has_more: response.has_more,
    };
  },

  async listByType(type: ModelType, params: SearchParams = {}): Promise<PaginatedResponse<ModelVM>> {
    return this.list({ ...params, type });
  },

  async get(modelId: string, includeCredentialsSchema: boolean = true, includeDisplayCredentials: boolean = true): Promise<ModelVM> {
    const url = `${MODEL_BASE_URL}/models/${modelId}?include_credentials_schema=${includeCredentialsSchema}&include_display_credentials=${includeDisplayCredentials}`;
    const response = await httpClient.get(url) as any as { data: ModelDto };
    return adaptModel(response.data);
  },

  async getModelSchema(modelSchemaId: string): Promise<ModelSchemaVM> {
    const url = `${MODEL_BASE_URL}/model_schemas/get?model_schema_id=${modelSchemaId}`;
    const response = await httpClient.get(url) as any as { data: ModelSchemaDto };
    return adaptModelSchema(response.data);
  },

  async listModelSchemas(offset: number = 0, limit: number = 100, providerId: string, type?: string): Promise<PaginatedResponse<ModelSchemaVM>> {
    let url = `${MODEL_BASE_URL}/model_schemas?offset=${offset}&limit=${limit}&provider_id=${providerId}`;
    if (type) {
      url += `&type=${type}`;
    }
    const response = await httpClient.get(url) as any as PaginatedResponse<ModelSchemaDto>;
    return {
      data: response.data.map(adaptModelSchema),
      has_more: response.has_more,
    };
  },

  async getProviderForm(providerId: string): Promise<{ credentials_schema: any }> {
    const url = `${MODEL_BASE_URL}/providers/get?provider_id=${providerId}`;
    const response = await httpClient.get(url) as any as { data: any };
    return response.data;
  },

  async listProviders(type?: string, limit: number = 100): Promise<PaginatedResponse<ProviderVM>> {
    let url = `${MODEL_BASE_URL}/providers?limit=${limit}`;
    if (type) {
      url += `&type=${type}`;
    }
    const response = await httpClient.get(url) as any as PaginatedResponse<ProviderDto>;
    return {
      data: adaptProviderList(response.data),
      has_more: response.has_more,
    };
  },

  async create(params: ModelCreateRequest): Promise<ModelVM> {
    const url = `${MODEL_BASE_URL}/models`;
    const response = await httpClient.post(url, params) as any as { data: ModelDto };
    return adaptModel(response.data);
  },

  async update(modelId: string, params: ModelUpdateRequest): Promise<ModelVM> {
    const url = `${MODEL_BASE_URL}/models/${modelId}`;
    const response = await httpClient.post(url, params) as any as { data: ModelDto };
    return adaptModel(response.data);
  },

  async delete(modelId: string): Promise<void> {
    const url = `${MODEL_BASE_URL}/models/${modelId}`;
    await httpClient.delete(url);
  },
};

export default modelService;
