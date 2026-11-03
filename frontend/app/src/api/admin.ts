import { apiGet, apiPost } from './client';
import type * as Contracts from '../shared/contracts/api';

export type TopicTrainingStatus = Contracts.TopicTrainingStatus;
export type MemberGraphStatus = Contracts.GraphBuildStatus;
export type IngestProgressJob = Contracts.IngestProgressJob;
export type BackfillProgress = Contracts.BackfillProgress;
export type IngestProgressResponse = Contracts.IngestProgressResponse;
export type JobStatusCounts = Contracts.JobStatusCounts;
export type GovInfoCoverage = Contracts.GovInfoCoverage;
export type StagingStatus = Contracts.StagingStatus;
export type AdminIngestSnapshot = Contracts.AdminIngestSnapshot;
export type IndexStatus = Contracts.IndexStatus;
export type SystemStatusResponse = Contracts.SystemStatusResponse;

export function fetchTopicTraining(): Promise<TopicTrainingStatus> {
    return apiGet<TopicTrainingStatus>('/api/v1/admin/topic-training');
}

export function startTopicTraining(): Promise<TopicTrainingStatus> {
    return apiPost<TopicTrainingStatus>('/api/v1/admin/topic-training');
}

export function fetchMemberGraph(): Promise<MemberGraphStatus> {
    return apiGet<MemberGraphStatus>('/api/v1/admin/member-graph');
}

export function startMemberGraph(): Promise<MemberGraphStatus> {
    return apiPost<MemberGraphStatus>('/api/v1/admin/member-graph');
}

export function fetchPerspectives(): Promise<MemberGraphStatus> {
    return apiGet<MemberGraphStatus>('/api/v1/admin/perspectives');
}

export function startPerspectives(): Promise<MemberGraphStatus> {
    return apiPost<MemberGraphStatus>('/api/v1/admin/perspectives');
}

export function fetchIngestProgress(): Promise<IngestProgressResponse> {
    return apiGet<IngestProgressResponse>('/api/v1/admin/ingest-progress');
}

export function fetchAdminIngestSnapshot(): Promise<AdminIngestSnapshot> {
    return apiGet<AdminIngestSnapshot>('/api/v1/admin/ingest-snapshot');
}

export function fetchSystemStatus(): Promise<SystemStatusResponse> {
    return apiGet<SystemStatusResponse>('/api/v1/admin/system-status');
}
