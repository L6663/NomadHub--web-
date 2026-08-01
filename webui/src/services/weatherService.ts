import type { WeatherLocation, WeatherSnapshot } from '@/types/models';

const LOCATION_KEY = 'nomadhub_weather_location';
const CACHE_KEY = 'nomadhub_weather_cache_v1';

const defaultLocation: WeatherLocation = {
  name: '淳安县', admin1: '浙江省', country: '中国', latitude: 29.608, longitude: 119.042,
};

interface GeocodingResponse { results?: Array<{ name: string; admin1?: string; country?: string; latitude: number; longitude: number; }>; }
interface ForecastResponse { current?: { temperature_2m?: number; relative_humidity_2m?: number; weather_code?: number; wind_speed_10m?: number; }; }
interface AirQualityResponse { current?: { us_aqi?: number; }; }

async function fetchWithTimeout(input: RequestInfo | URL, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try { return await fetch(input, { signal: controller.signal }); }
  finally { window.clearTimeout(timer); }
}

export function getSavedWeatherLocation(): WeatherLocation {
  try { const raw = localStorage.getItem(LOCATION_KEY); return raw ? JSON.parse(raw) as WeatherLocation : defaultLocation; }
  catch { return defaultLocation; }
}
export function saveWeatherLocation(location: WeatherLocation) { localStorage.setItem(LOCATION_KEY, JSON.stringify(location)); }

export async function searchWeatherLocations(keyword: string): Promise<WeatherLocation[]> {
  const query = keyword.trim(); if (query.length < 2) return [];
  const url = new URL('https://geocoding-api.open-meteo.com/v1/search');
  url.searchParams.set('name', query); url.searchParams.set('count', '5'); url.searchParams.set('language', 'zh'); url.searchParams.set('format', 'json');
  const response = await fetchWithTimeout(url, 6000);
  if (!response.ok) throw new Error(`地理编码请求失败：${response.status}`);
  const payload = await response.json() as GeocodingResponse;
  return (payload.results ?? []).map((item) => ({ name:item.name, admin1:item.admin1, country:item.country, latitude:item.latitude, longitude:item.longitude }));
}

export function weatherCodeText(code: number | null): string {
  if (code === null) return '未知'; if (code === 0) return '晴'; if ([1,2].includes(code)) return '少云'; if (code === 3) return '阴';
  if ([45,48].includes(code)) return '雾'; if ([51,53,55,56,57].includes(code)) return '毛毛雨'; if ([61,63,65,66,67].includes(code)) return '降雨';
  if ([71,73,75,77].includes(code)) return '降雪'; if ([80,81,82].includes(code)) return '阵雨'; if ([85,86].includes(code)) return '阵雪'; if ([95,96,99].includes(code)) return '雷暴';
  return '天气变化';
}

function readCache(): WeatherSnapshot | null { try { const raw=localStorage.getItem(CACHE_KEY); return raw ? JSON.parse(raw) as WeatherSnapshot : null; } catch { return null; } }

export async function fetchWeather(location = getSavedWeatherLocation()): Promise<WeatherSnapshot> {
  const forecast = new URL('https://api.open-meteo.com/v1/forecast');
  forecast.searchParams.set('latitude', String(location.latitude)); forecast.searchParams.set('longitude', String(location.longitude));
  forecast.searchParams.set('current','temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m'); forecast.searchParams.set('timezone','auto');
  const air = new URL('https://air-quality-api.open-meteo.com/v1/air-quality');
  air.searchParams.set('latitude', String(location.latitude)); air.searchParams.set('longitude', String(location.longitude)); air.searchParams.set('current','us_aqi'); air.searchParams.set('timezone','auto');
  try {
    const [forecastResponse, airResponse] = await Promise.all([fetchWithTimeout(forecast,7000), fetchWithTimeout(air,7000)]);
    if (!forecastResponse.ok) throw new Error(`天气请求失败：${forecastResponse.status}`);
    const forecastData = await forecastResponse.json() as ForecastResponse;
    const airData = airResponse.ok ? await airResponse.json() as AirQualityResponse : {};
    const snapshot: WeatherSnapshot = { location, temperature:forecastData.current?.temperature_2m ?? null, humidity:forecastData.current?.relative_humidity_2m ?? null, windSpeed:forecastData.current?.wind_speed_10m ?? null, weatherCode:forecastData.current?.weather_code ?? null, aqi:airData.current?.us_aqi ?? null, updatedAt:Date.now(), source:'network' };
    localStorage.setItem(CACHE_KEY, JSON.stringify(snapshot)); return snapshot;
  } catch {
    const cached=readCache(); if (cached) return { ...cached, source:'cache' };
    return { location, temperature:null, humidity:null, windSpeed:null, weatherCode:null, aqi:null, updatedAt:Date.now(), source:'unavailable' };
  }
}
