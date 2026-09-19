import { apiGet } from './client';

export type TopicSummary = {
  topic_id: number;
  name: string;
  label: string;
  size: number;
  top_words: string[];
};

export type TopicsResponse = {
  topics: TopicSummary[];
  model_version: string | null;
  trained_at: string | null;
};

export type TopicTrendPoint = {
  timestamp: string;
  frequency: number;
  words: string | null;
};

export type TopicBill = {
  bill_id: string;
  title: string | null;
  probability: number;
};

export type TopicDetailResponse = {
  topic: TopicSummary;
  model_version: string | null;
  trend: TopicTrendPoint[];
  top_bills: TopicBill[];
};

export type TopicAssignmentItem = {
  topic_id: number;
  label: string;
  probability: number;
};

export type BillTopicsResponse = {
  bill_id: string;
  topics: TopicAssignmentItem[];
  model_version: string | null;
};

export type MemberTopicTrendPoint = {
  period: string;
  topic_id: number;
  label: string;
  count: number;
};

export type MemberTopicsResponse = {
  bioguide_id: string;
  topics: { label: string; weight: number }[];
  trend: MemberTopicTrendPoint[];
  model_version: string | null;
  subjects: { label: string; weight: number }[];
  policy_areas: { label: string; weight: number }[];
};

export type TopicTrendSeries = {
  topic_id: number;
  label: string;
  points: TopicTrendPoint[];
};

export type TopicTrendsResponse = {
  series: TopicTrendSeries[];
  model_version: string | null;
};

export function fetchTopics(): Promise<TopicsResponse> {
  return apiGet<TopicsResponse>('/api/v1/topics');
}

export function fetchTopicTrends(size = 8): Promise<TopicTrendsResponse> {
  return apiGet<TopicTrendsResponse>(`/api/v1/topics/trends?size=${size}`);
}

export function fetchTopic(topicId: number): Promise<TopicDetailResponse> {
  return apiGet<TopicDetailResponse>(`/api/v1/topics/${topicId}`);
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
