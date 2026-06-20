import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { toast } from 'react-toastify';
import { ApiErrorResponse, AppError } from './types';

const createHttpClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: '/',
    timeout: 60000,
  });

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

export type HttpClient = typeof httpClient;
export type RequestConfig = AxiosRequestConfig;
