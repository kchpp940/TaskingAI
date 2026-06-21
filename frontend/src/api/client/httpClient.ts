import axios, { AxiosInstance, AxiosRequestConfig, AxiosError, AxiosInterceptorManager, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { toast } from 'react-toastify';
import { ApiErrorResponse, AppError } from './types';

export interface TypedHttpClient {
  interceptors: {
    request: AxiosInterceptorManager<InternalAxiosRequestConfig>;
    response: AxiosInterceptorManager<AxiosResponse>;
  };
  defaults: AxiosInstance['defaults'];

  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  head<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  options<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
}

const createHttpClient = (): TypedHttpClient => {
  const client = axios.create({
    baseURL: '/',
    timeout: 60000,
  }) as unknown as TypedHttpClient;

  client.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error),
  );

  client.interceptors.response.use(
    (response) => response.data,
    (error: AxiosError<ApiErrorResponse>) => {
      const location = window.location.href;

      if (!error.response) {
        toast.error('Connection failed. Please retry.');
        return Promise.reject(new AppError('Connection failed. Please retry.', 'CONNECTION_FAILED'));
      }

      const { status, data } = error.response;

      if (
        status === 401 &&
        !location.includes('/auth/signin') &&
        data?.error?.code === 'TOKEN_VALIDATION_FAILED'
      ) {
        localStorage.removeItem('token');
        window.location.href = '/auth/signin';
      }

      const appError = new AppError(
        data?.error?.message || error.message,
        data?.error?.code || 'REQUEST_FAILED',
        status,
      );

      return Promise.reject(appError);
    },
  );

  return client;
};

export const httpClient = createHttpClient();

export const extractErrorMessage = (error: unknown): string => {
  if (error instanceof AppError) {
    return error.message;
  }
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    return axiosError.response?.data?.error?.message || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
};

export const handleApiError = (error: unknown): string => {
  const message = extractErrorMessage(error);
  toast.error(message);
  return message;
};

export type HttpClient = TypedHttpClient;
export type RequestConfig = AxiosRequestConfig;
