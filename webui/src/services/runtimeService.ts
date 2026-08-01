import { getApi } from '@/services/socketApi';
import type { DeviceItem, GatewayRuntime, RuntimeOverview, RuntimeSample } from '@/types/models';

export async function fetchRuntimeOverview(): Promise<RuntimeOverview> {
  const response = await getApi<RuntimeOverview>('/dashboard/overview');
  if (response.code !== 0 || !response.data) throw new Error(response.message || '总览数据不可用');
  return response.data;
}

export async function fetchRuntimeSamples(): Promise<RuntimeSample[]> {
  const response = await getApi<RuntimeSample[]>('/runtime/samples');
  if (response.code !== 0 || !Array.isArray(response.data)) return [];
  return response.data;
}

export async function fetchGatewayRuntime(): Promise<GatewayRuntime> {
  const response = await getApi<GatewayRuntime>('/gateway/status');
  if (response.code !== 0 || !response.data) throw new Error(response.message || '网关状态不可用');
  return response.data;
}

export async function fetchDevices(): Promise<DeviceItem[]> {
  const response = await getApi<DeviceItem[]>('/devices');
  if (response.code !== 0 || !Array.isArray(response.data)) return [];
  return response.data;
}
