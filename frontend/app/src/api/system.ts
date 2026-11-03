import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type HealthResponse = Contracts.HealthResponse;
export type ReadinessResponse = Contracts.ReadinessResponse;

export function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health');
}

export function fetchReadiness(): Promise<ReadinessResponse> {
  return apiGet<ReadinessResponse>('/ready');
}
