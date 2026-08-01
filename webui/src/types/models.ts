/**
 * 页面使用的数据模型。
 *
 * 后续对接网关时，服务端 JSON 字段必须与这些类型保持一致；这样可以在编译阶段
 * 发现字段拼写和类型错误，避免不同成员联调时依靠“猜字段”。
 */
export type HealthState = 'normal' | 'warning' | 'danger' | 'offline' | 'info';

export interface MetricItem {
  key: string;
  label: string;
  value: string;
  note: string;
  icon: string;
  state: HealthState;
}

export interface DeviceItem {
  id: string;
  name: string;
  serial: string;
  type: string;
  online: boolean;
  signal: number;
  firmware: string;
  heartbeat: string;
  icon: string;
}

export interface SceneItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  active: boolean;
}

export interface AlertItem {
  id: string;
  name: string;
  description: string;
  level: '严重' | '较高' | '中等' | '信息';
  source: string;
  area: string;
  time: string;
  status: '未处理' | '处理中' | '已确认' | '已恢复';
  icon: string;
}

export interface GatewayService {
  name: string;
  description: string;
  running: boolean;
  pid: number;
  cpu: number;
  memory: number;
  icon: string;
}

export interface UserItem {
  id: number;
  name: string;
  username: string;
  role: string;
  online: boolean;
  lastLogin: string;
  phone: string;
  email: string;
  permissionGroup: string;
  avatar: string;
}

export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  mock?: boolean;
}

export interface RuntimeOverview {
  temperature: number;
  humidity: number;
  smoke: number;
  light: number;
  flame: boolean;
  pir: boolean;
  fan: boolean;
  lamp: boolean;
  buzzer: boolean;
  relay: boolean;
  safetyState: number;
  u5Online: boolean;
  rct6Online: boolean;
  gatewayOnline: boolean;
  hasDeviceData: boolean;
  sequence: number;
  updatedAt: number;
  rs485: string;
  modbusRole: string;
  metrics: MetricItem[];
}

export interface VehicleModuleMetric {
  label: string;
  value: string | number;
  unit?: string;
}

export interface VehicleModuleAction {
  id: string;
  label: string;
  enabled: boolean;
  danger?: boolean;
}

export interface VehicleModule {
  id: string;
  name: string;
  icon: string;
  status: HealthState;
  summary: string;
  hotspot: { x: number; y: number };
  metrics: VehicleModuleMetric[];
  actions: VehicleModuleAction[];
  updatedAt?: number;
}

export interface WeatherLocation {
  name: string;
  admin1?: string;
  country?: string;
  latitude: number;
  longitude: number;
}

export interface WeatherSnapshot {
  location: WeatherLocation;
  temperature: number | null;
  humidity: number | null;
  windSpeed: number | null;
  weatherCode: number | null;
  aqi: number | null;
  updatedAt: number;
  source: 'network' | 'cache' | 'unavailable';
}

export interface GatewayRuntime {
  load1m: number;
  memoryUsedPercent: number;
  diskUsedPercent: number;
  uptimeSeconds: number;
  ipv4: string;
  hostname: string;
  httpPort: number;
  rawTcpPort: number;
  rs485: string;
}

export interface RuntimeSample {
  temperature: number;
  humidity: number;
  smoke: number;
  light: number;
  timestamp: number;
}

export interface LoginResult {
  token: string;
  username: string;
  role: string;
  expiresIn: number;
}

export interface RegisterResult {
  userId: number;
  username: string;
}
