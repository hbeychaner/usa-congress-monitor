import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type StateSummary = Contracts.StateSummary;
export type TimelineMember = Contracts.TimelineMember;
export type StateTimelineResponse = Contracts.StateTimelineResponse;
export type DistrictFeatureCollection = Contracts.DistrictFeatureCollection;
export type TimelineFilters = {
    fromCongress?: number;
    toCongress?: number;
};

export function fetchStates(): Promise<StateSummary[]> {
    return apiGet<StateSummary[]>('/api/v1/states');
}

export function fetchStateDistricts(stateCode: string): Promise<DistrictFeatureCollection> {
    return apiGet<DistrictFeatureCollection>(`/api/v1/states/${stateCode}/districts`);
}

export function fetchStateTimeline(stateCode: string, filters: TimelineFilters = {}): Promise<StateTimelineResponse> {
    const params = new URLSearchParams();
    if (typeof filters.fromCongress === 'number') {
        params.set('from_congress', String(filters.fromCongress));
    }
    if (typeof filters.toCongress === 'number') {
        params.set('to_congress', String(filters.toCongress));
    }
    const query = params.toString();
    const path = query
        ? `/api/v1/states/${stateCode}/timeline?${query}`
        : `/api/v1/states/${stateCode}/timeline`;

    return apiGet<StateTimelineResponse>(path);
}
