import { apiGet } from './client';
import type { components } from '../shared/contracts/api';

export type SearchResponse = components['schemas']['SearchResponse'];

export type SearchParams = {
    query: string;
    types: string[];
    limit: number;
};

export function fetchSearch(params: SearchParams): Promise<SearchResponse> {
    const queryParams = new URLSearchParams({
        q: params.query,
        types: params.types.join(','),
        limit: String(params.limit),
    });
    return apiGet<SearchResponse>(`/api/v1/search?${queryParams.toString()}`);
}
