import { apiGet } from './client';

export type CommitteeActivity = {
    name: string;
    date: string | null;
};

export type CommitteeBill = {
    bill_id: string;
    title: string;
    congress: number | null;
    chamber: string | null;
    activities: CommitteeActivity[];
};

export type CommitteeDetailResponse = {
    system_code: string;
    name: string;
    chamber: string | null;
    committee_type: string | null;
    total: number;
    page: number;
    limit: number;
    bills: CommitteeBill[];
};

export function fetchCommittee(systemCode: string, page = 1, limit = 50): Promise<CommitteeDetailResponse> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    return apiGet<CommitteeDetailResponse>(`/api/v1/committees/${encodeURIComponent(systemCode)}?${params.toString()}`);
}
