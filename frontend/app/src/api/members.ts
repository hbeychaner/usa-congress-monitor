import { apiGet } from './client';
import type { components } from '../shared/contracts/api';

export type MemberProfileResponse = components['schemas']['MemberProfileResponse'];
export type MemberSummary = components['schemas']['MemberSummary'];
export type MemberActivityResponse = components['schemas']['MemberActivityResponse'];
export type MemberActivityItem = components['schemas']['MemberActivityItem'];
export type MembersResponse = {
    members: MemberSummary[];
    total: number;
    page: number;
    limit: number;
};

export type MemberFilters = {
    query?: string;
    state?: string;
    chamber?: string;
    party?: string;
};

export function fetchMembers(page = 1, limit = 50, filters: MemberFilters = {}): Promise<MembersResponse> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (filters.query?.trim()) params.set('query', filters.query.trim());
    if (filters.state) params.set('state', filters.state);
    if (filters.chamber) params.set('chamber', filters.chamber);
    if (filters.party) params.set('party', filters.party);
    return apiGet<MembersResponse>(`/api/v1/members?${params.toString()}`);
}

export function fetchMemberProfile(bioguideId: string): Promise<MemberProfileResponse> {
    return apiGet<MemberProfileResponse>(`/api/v1/members/${bioguideId}`);
}

export function fetchMemberActivity(
    bioguideId: string,
    page = 1,
    limit = 25,
    types?: string,
): Promise<MemberActivityResponse> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (types) params.set('types', types);
    return apiGet<MemberActivityResponse>(
        `/api/v1/members/${bioguideId}/activity?${params.toString()}`,
    );
}
