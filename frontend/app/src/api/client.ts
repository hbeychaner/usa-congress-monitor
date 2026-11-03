import type { AnalysisState } from './analysis';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(readonly status: number, message: string, readonly analysisState?: AnalysisState) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, method: 'GET' | 'POST'): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method });
  if (!response.ok) {
    let detail: unknown;
    let analysisState: AnalysisState | undefined;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === 'object' && 'detail' in body) detail = body.detail;
      if (body && typeof body === 'object' && 'analysis_state' in body
        && (body.analysis_state === 'not_built' || body.analysis_state === 'unavailable')) {
        analysisState = body.analysis_state;
      }
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((issue: unknown) =>
        issue && typeof issue === 'object' && 'msg' in issue && typeof issue.msg === 'string'
          ? issue.msg : '').filter(Boolean).join('; ') : '';
    throw new ApiError(response.status, message || `Request failed: ${response.status}`, analysisState);
  }
  return (await response.json()) as T;
}

export function apiPost<T>(path: string): Promise<T> {
  return request<T>(path, 'POST');
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, 'GET');
}
