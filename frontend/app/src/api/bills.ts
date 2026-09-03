import { apiGet } from './client';
import type { components } from '../shared/contracts/api';

export type BillSummary = {
  bill_id: string;
  title: string;
  congress: number | null;
  bill_type: string | null;
  number: number | null;
  chamber: string | null;
  updated_at?: string | null;
};

export type BillsResponse = {
  bills: BillSummary[];
  total: number;
};

export type BillDetailResponse = components['schemas']['BillDetailResponse'];

export type BillFilters = {
  query?: string;
  congress?: string;
  chamber?: string;
  billType?: string;
};

export function fetchRecentBills(limit = 50, page = 1, filters: BillFilters = {}): Promise<BillsResponse> {
    const params = new URLSearchParams({ limit: String(limit), page: String(page) });
    if (filters.query) params.set('query', filters.query);
    if (filters.congress) params.set('congress', filters.congress);
    if (filters.chamber) params.set('chamber', filters.chamber);
    if (filters.billType) params.set('bill_type', filters.billType);
    return apiGet<BillsResponse>(`/api/v1/bills/recent?${params.toString()}`);
}

export function fetchBill(billId: string): Promise<BillDetailResponse> {
  return apiGet<BillDetailResponse>(`/api/v1/bills/${encodeURIComponent(billId)}`);
}