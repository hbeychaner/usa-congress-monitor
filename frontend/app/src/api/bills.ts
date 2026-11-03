import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type BillSummary = Contracts.BillSummary;
export type BillsResponse = Contracts.BillsResponse;
export type BillDetailResponse = Contracts.BillDetailResponse;
export type BillVotesResponse = Contracts.BillVotesResponse;

export type SimilarBill = Contracts.SimilarBill;
export type SimilarBillsResponse = Contracts.SimilarBillsResponse;

export type BillFilters = {
  query?: string;
  congress?: string;
  chamber?: string;
  billType?: string;
  subject?: string;
  hasVotes?: boolean;
};

export function fetchRecentBills(limit = 50, page = 1, filters: BillFilters = {}): Promise<BillsResponse> {
    const params = new URLSearchParams({ limit: String(limit), page: String(page) });
    if (filters.query) params.set('query', filters.query);
    if (filters.congress) params.set('congress', filters.congress);
    if (filters.chamber) params.set('chamber', filters.chamber);
    if (filters.billType) params.set('bill_type', filters.billType);
    if (filters.subject) params.set('subject', filters.subject);
    if (filters.hasVotes) params.set('has_votes', 'true');
    return apiGet<BillsResponse>(`/api/v1/bills/recent?${params.toString()}`);
}

export function fetchBill(billId: string): Promise<BillDetailResponse> {
  return apiGet<BillDetailResponse>(`/api/v1/bills/${encodeURIComponent(billId)}`);
}

export function fetchBillVotes(billId: string): Promise<BillVotesResponse> {
  return apiGet<BillVotesResponse>(`/api/v1/bills/${encodeURIComponent(billId)}/votes`);
}

export function fetchSimilarBills(billId: string, limit = 8): Promise<SimilarBillsResponse> {
  return apiGet<SimilarBillsResponse>(`/api/v1/bills/${encodeURIComponent(billId)}/similar?limit=${limit}`);
}