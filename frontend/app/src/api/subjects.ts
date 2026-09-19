import { apiGet } from './client';

export type SubjectCount = {
    name: string;
    count: number;
};

export type SubjectsResponse = {
    subjects: SubjectCount[];
    policy_areas: SubjectCount[];
    total_bills: number;
};

export function fetchSubjects(congress?: number, size = 100): Promise<SubjectsResponse> {
    const params = new URLSearchParams({ size: String(size) });
    if (congress) params.set('congress', String(congress));
    return apiGet<SubjectsResponse>(`/api/v1/subjects?${params.toString()}`);
}

export type PolicyAreaTrendPoint = {
    year: number;
    count: number;
};

export type PolicyAreaTrendSeries = {
    name: string;
    total: number;
    points: PolicyAreaTrendPoint[];
};

export type PolicyAreaTrendsResponse = {
    series: PolicyAreaTrendSeries[];
    total_bills: number;
};

export function fetchPolicyAreaTrends(size = 10, startYear?: number): Promise<PolicyAreaTrendsResponse> {
    const params = new URLSearchParams({ size: String(size) });
    if (startYear) params.set('start_year', String(startYear));
    return apiGet<PolicyAreaTrendsResponse>(`/api/v1/subjects/policy-area-trends?${params.toString()}`);
}
