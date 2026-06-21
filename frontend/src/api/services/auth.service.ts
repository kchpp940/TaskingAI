import { httpClient, API_BASE_URL } from '../client';

const AUTH_BASE_URL = `${API_BASE_URL}`;

export interface LoginParams {
  username?: string;
  email?: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  [key: string]: any;
}

export interface VerifyTokenResponse {
  valid: boolean;
  [key: string]: any;
}

export const authService = {
  async login(params: LoginParams): Promise<LoginResponse> {
    const url = `${AUTH_BASE_URL}/admins/login`;
    const response = await httpClient.post<LoginResponse>(url, params);
    return response;
  },

  async verifyToken(): Promise<VerifyTokenResponse> {
    const url = `${AUTH_BASE_URL}/admins/verify_token`;
    const response = await httpClient.post<VerifyTokenResponse>(url);
    return response;
  },

  async fetchIcon(providerId: string): Promise<string> {
    const url = `/images/providers/icons/${providerId}.svg`;
    const response = await httpClient.get<string>(url, { responseType: 'text' as any });
    return response;
  },

  async getViewCode(module: string): Promise<{ data: string }> {
    const url = `${AUTH_BASE_URL}/ui/template_codes/get_code?module=${module}`;
    const response = await httpClient.get<{ data: string }>(url);
    return response;
  },

  async chatCompletion(params: any): Promise<any> {
    const url = `${AUTH_BASE_URL}/inference/chat_completion`;
    const response = await httpClient.post<any>(url, params);
    return response;
  },
};

export default authService;
