import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type SubjectCount = Contracts.SubjectCount;
export type SubjectsResponse = Contracts.SubjectsResponse;
export type PolicyAreaTrendPoint = Contracts.PolicyAreaTrendPoint;
export type PolicyAreaTrendSeries = Contracts.PolicyAreaTrendSeries;
export type PolicyAreaTrendsResponse = Contracts.PolicyAreaTrendsResponse;

export function fetchSubjects(congress?: number, size = 100): Promise<SubjectsResponse> {
    const params = new URLSearchParams({ size: String(size) });
    if (congress) params.set('congress', String(congress));
    return apiGet<SubjectsResponse>(`/api/v1/subjects?${params.toString()}`);
}

export function fetchPolicyAreaTrends(size = 10, startYear?: number): Promise<PolicyAreaTrendsResponse> {
    const params = new URLSearchParams({ size: String(size) });
    if (startYear) params.set('start_year', String(startYear));
    return apiGet<PolicyAreaTrendsResponse>(`/api/v1/subjects/policy-area-trends?${params.toString()}`);
}
