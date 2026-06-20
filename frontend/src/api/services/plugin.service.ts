import { httpClient, API_BASE_URL, buildListParams, DEFAULT_LIMIT, PaginatedResponse, SearchParams } from '../client';
import {
  BundleInstanceDto,
  BundleInstanceVM,
  BundleDto,
  BundleVM,
  PluginDto,
  PluginVM,
  BundleInstanceCreateRequest,
  BundleInstanceUpdateRequest,
} from '../viewmodels';
import { adaptBundle, adaptBundleInstance, adaptBundleInstanceList, adaptPlugin, adaptPluginList } from '../adapters';

const PLUGIN_BASE_URL = `${API_BASE_URL}`;

export interface BundleInstanceListParams extends SearchParams {}

export interface BundleListParams {
  limit?: number;
  offset?: number;
  lang?: string;
}

export const pluginService = {
  async listBundleInstances(params: BundleInstanceListParams = {}): Promise<PaginatedResponse<BundleInstanceVM>> {
    const query = buildListParams('bundle_instance_id', { limit: DEFAULT_LIMIT, ...params });
    const url = `${PLUGIN_BASE_URL}/bundle_instances${query ? `?${query}` : ''}`;
    const response = await httpClient.get<PaginatedResponse<BundleInstanceDto>>(url);
    return {
      data: adaptBundleInstanceList(response.data),
      has_more: response.has_more,
    };
  },

  async listBundles(params: BundleListParams = {}): Promise<PaginatedResponse<BundleVM>> {
    const defaultParams = { limit: 100, offset: 0, lang: 'en', ...params };
    const query = Object.entries(defaultParams)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    const url = `${PLUGIN_BASE_URL}/bundles${query ? `?${query}` : ''}`;
    const response = await httpClient.get<PaginatedResponse<BundleDto>>(url);
    return {
      data: response.data.map(adaptBundle),
      has_more: response.has_more,
    };
  },

  async getBundlePlugins(bundleId: string): Promise<PluginVM[]> {
    const url = `${PLUGIN_BASE_URL}/plugins?bundle_id=${bundleId}`;
    const response = await httpClient.get<{ data: PluginDto[] }>(url);
    return adaptPluginList(response.data);
  },

  async createBundleInstance(params: BundleInstanceCreateRequest): Promise<BundleInstanceVM> {
    const url = `${PLUGIN_BASE_URL}/bundle_instances`;
    const response = await httpClient.post<{ data: BundleInstanceDto }>(url, params);
    return adaptBundleInstance(response.data);
  },

  async updateBundleInstance(bundleInstanceId: string, params: BundleInstanceUpdateRequest): Promise<BundleInstanceVM> {
    const url = `${PLUGIN_BASE_URL}/bundle_instances/${bundleInstanceId}`;
    const response = await httpClient.post<{ data: BundleInstanceDto }>(url, params);
    return adaptBundleInstance(response.data);
  },

  async deleteBundleInstance(bundleInstanceId: string): Promise<void> {
    const url = `${PLUGIN_BASE_URL}/bundle_instances/${bundleInstanceId}`;
    await httpClient.delete(url);
  },
};

export default pluginService;
