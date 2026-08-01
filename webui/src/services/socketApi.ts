import axios, { AxiosError } from 'axios';
import type { ApiEnvelope } from '@/types/models';

export const TOKEN_KEY = 'nomadhub_token';

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' },
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiEnvelope<unknown>>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (!location.pathname.startsWith('/login')) location.assign('/login');
    }
    return Promise.reject(error);
  },
);

/**
 * 浏览器不能直接建立任意原始TCP连接，因此Web端通过HTTP访问Linux C后端。
 * HTTP底层仍然使用TCP；Qt和调试程序则使用后端9000端口的JSON Lines协议。
 */
export async function getApi<T>(path: string): Promise<ApiEnvelope<T>> {
  try {
    const response = await http.get<ApiEnvelope<T>>(path);
    return response.data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export async function postApi<T>(path: string, payload?: unknown): Promise<ApiEnvelope<T>> {
  try {
    const response = await http.post<ApiEnvelope<T>>(path, payload ?? {});
    return response.data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export function normalizeApiError(error: unknown): Error {
  if (axios.isAxiosError<ApiEnvelope<unknown>>(error)) {
    const message = error.response?.data?.message;
    if (message) return new Error(message);
    if (error.code === 'ECONNABORTED') return new Error('网关响应超时，请检查Linux服务。');
    if (!error.response) return new Error('无法连接Linux网关，请确认8080端口服务已启动。');
    return new Error(`请求失败：HTTP ${error.response.status}`);
  }
  return error instanceof Error ? error : new Error('未知通信错误');
}
