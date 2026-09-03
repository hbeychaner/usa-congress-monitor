import { apiGet } from './client';

export type HealthResponse = {
  status: string;
};

export function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health');
}
