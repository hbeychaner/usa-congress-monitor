import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type CommitteeActivity = Contracts.CommitteeActivity;
export type CommitteeBill = Contracts.CommitteeBill;
export type CommitteeDetailResponse = Contracts.CommitteeDetailResponse;

export function fetchCommittee(systemCode: string, page = 1, limit = 50): Promise<CommitteeDetailResponse> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    return apiGet<CommitteeDetailResponse>(`/api/v1/committees/${encodeURIComponent(systemCode)}?${params.toString()}`);
}
