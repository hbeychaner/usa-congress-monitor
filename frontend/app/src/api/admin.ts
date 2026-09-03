import { apiGet } from './client';

export type IngestProgressJob = {
    job_id: string;
    status: string;
    resource: string;
    from_date: string | null;
    to_date: string | null;
    fetch_items: boolean;
    hydrated: number;
    discovered: number;
    target: number;
    remaining: number;
};

export type IngestProgressResponse = {
    hydrated: number;
    discovered: number;
    target: number;
    remaining: number;
    active_jobs: number;
    jobs: IngestProgressJob[];
};

export type JobStatusCounts = {
    queued: number;
    running: number;
    retrying: number;
    succeeded: number;
    failed: number;
};

export type GovInfoCoverage = {
    congress: number;
    expected: number;
    available: number;
    pending: number;
    failed: number;
    not_available: number;
    complete: boolean;
    report_found: boolean;
};

export type StagingStatus = {
    index: string;
    exists: boolean;
    documents: number;
    production_alias_target: string | null;
    connected: boolean;
};

export type AdminIngestSnapshot = {
    congress: number;
    govinfo: GovInfoCoverage;
    govinfo_jobs: JobStatusCounts;
    govinfo_batch_jobs: JobStatusCounts;
    index_jobs: JobStatusCounts;
    reconcile_jobs: JobStatusCounts;
    staging: StagingStatus;
    ready_for_reconciliation: boolean;
    ready_for_cutover: boolean;
};

export function fetchIngestProgress(): Promise<IngestProgressResponse> {
    return apiGet<IngestProgressResponse>('/api/v1/admin/ingest-progress');
}

export function fetchAdminIngestSnapshot(): Promise<AdminIngestSnapshot> {
    return apiGet<AdminIngestSnapshot>('/api/v1/admin/ingest-snapshot');
}
