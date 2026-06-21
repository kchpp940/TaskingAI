export { httpClient, extractErrorMessage, handleApiError } from './httpClient';
export type { HttpClient, RequestConfig, TypedHttpClient } from './httpClient';
export { buildPrefixFilter, buildQueryString, buildListParams } from './queryBuilder';
export {
  API_BASE_URL,
  DEFAULT_LIMIT,
} from './types';
export type {
  ApiErrorDetail,
  ApiErrorResponse,
  AppError,
  PaginatedResponse,
  PaginationParams,
  SearchParams,
} from './types';
