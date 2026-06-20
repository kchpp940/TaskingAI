export interface ApiErrorDetail {
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export class AppError extends Error {
  code: string;
  status?: number;

  constructor(message: string, code: string = 'UNKNOWN_ERROR', status?: number) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.status = status;
  }
}

export interface PaginatedResponse<T> {
  data: T[];
  has_more: boolean;
}

export interface PaginationParams {
  offset?: number;
  limit?: number;
}

export interface SearchParams extends PaginationParams {
  name_search?: string;
  id_search?: string;
}

export const API_BASE_URL = 'api/v1';

export const DEFAULT_LIMIT = 20;
