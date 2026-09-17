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
