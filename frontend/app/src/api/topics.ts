import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type TopicSummary = Contracts.TopicSummary;
export type TopicsResponse = Contracts.TopicsResponse;
export type TopicTrendPoint = Contracts.TopicTrendPoint;
export type TopicBill = Contracts.TopicBill;
export type RelatedTopic = Contracts.RelatedTopic;
export type TopicDetailResponse = Contracts.TopicDetailResponse;
export type TopicAssignmentItem = Contracts.TopicAssignmentItem;
export type BillTopicsResponse = Contracts.BillTopicsResponse;
export type MemberTopicTrendPoint = Contracts.MemberTopicTrendPoint;
export type MemberTopicsResponse = Contracts.MemberTopicsResponse;
export type TopicTrendSeries = Contracts.TopicTrendSeries;
export type TopicTrendsResponse = Contracts.TopicTrendsResponse;
export type MetasubjectSummary = Contracts.MetasubjectSummary;
export type MetasubjectsResponse = Contracts.MetasubjectsResponse;
export type MetasubjectTrendSeries = Contracts.MetasubjectTrendSeries;
export type MetasubjectTrendsResponse = Contracts.MetasubjectTrendsResponse;
export type RelatedMetasubject = Contracts.RelatedMetasubject;
export type MetasubjectDetailResponse = Contracts.MetasubjectDetailResponse;

export function fetchMetasubjects(): Promise<MetasubjectsResponse> {
  return apiGet<MetasubjectsResponse>('/api/v1/topics/metasubjects');
}

export function fetchMetasubject(metasubjectId: number): Promise<MetasubjectDetailResponse> {
  return apiGet<MetasubjectDetailResponse>(`/api/v1/topics/metasubjects/${metasubjectId}`);
}

export function fetchMetasubjectTrends(): Promise<MetasubjectTrendsResponse> {
  return apiGet<MetasubjectTrendsResponse>('/api/v1/topics/metasubjects/trends');
}

export function fetchTopics(): Promise<TopicsResponse> {
  return apiGet<TopicsResponse>('/api/v1/topics');
}

export function fetchTopicTrends(size = 8): Promise<TopicTrendsResponse> {
  return apiGet<TopicTrendsResponse>(`/api/v1/topics/trends?size=${size}`);
}

export function fetchTopic(topicId: number, bills = 20): Promise<TopicDetailResponse> {
  return apiGet<TopicDetailResponse>(`/api/v1/topics/${topicId}?bills=${bills}`);
}

export function fetchBillTopics(billId: string): Promise<BillTopicsResponse> {
  return apiGet<BillTopicsResponse>(
    `/api/v1/bills/${encodeURIComponent(billId)}/topics`,
  );
}

export function fetchMemberTopics(bioguideId: string): Promise<MemberTopicsResponse> {
  return apiGet<MemberTopicsResponse>(
    `/api/v1/members/${encodeURIComponent(bioguideId)}/topics`,
  );
}
