import { apiGet } from './client';

export type IngestProgressJob = {
    job_id: string;
    status: string;
    resource: string;
    congress: number | null;
    from_date: string | null;
    to_date: string | null;
    fetch_items: boolean;
    hydrated: number;
    discovered: number;
    target: number;
    remaining: number;
};

export type BackfillProgress = {
    total: number;
    succeeded: number;
    pending: number;
    failed: number;
    percent: number;
    rate_per_hour: number;
    eta: string | null;
    batches_pending: number;
};

export type IngestProgressResponse = {
    hydrated: number;
    discovered: number;
    target: number;
    remaining: number;
    active_jobs: number;
    activity: 'continuing' | 'stalled' | 'waiting' | 'queued' | 'idle';
    last_progress_at: string | null;
    jobs: IngestProgressJob[];
    backfill: BackfillProgress | null;
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

export type IndexStatus = {
    name: string;
    documents: number;
};

export type SystemStatusResponse = {
    search_connected: boolean;
    indices: IndexStatus[];
    jobs: Record<string, JobStatusCounts>;
    generated_at: string | null;
};

export function fetchSystemStatus(): Promise<SystemStatusResponse> {
    return apiGet<SystemStatusResponse>('/api/v1/admin/system-status');
}
