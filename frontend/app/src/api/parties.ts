import { apiGet } from './client';

import type { PartyGroup } from './graph';

export type PartyTopicEntry = {
  topic_id: number;
  label: string;
  bills: number;
  topic_bills: number;
  share_of_party: number;
  share_of_topic: number;
  summary: string;
};

export type PartyRanking = {
  party: PartyGroup;
  total_bills: number;
  topics: PartyTopicEntry[];
};

export type BilateralTopicEntry = {
  topic_id: number;
  label: string;
  bills: number;
  bipartisan_bills: number;
  share: number;
  terms: TermUse[];
  subjects: SubjectUse[];
  summary: string;
};

export type PartiesResponse = {
  congress: number | null;
  congresses: number[];
  model_version: string | null;
  parties: PartyRanking[];
  bilateral: BilateralTopicEntry[];
};

export type BillRef = {
  doc_id: string;
  title: string;
};

export type TermUse = {
  term: string;
  bills: number;
  sponsors: number;
  examples: BillRef[];
};

export type SubjectUse = {
  name: string;
  bills: number;
  share: number;
};

export type PartyTerms = {
  party: PartyGroup;
  bills: number;
  terms: TermUse[];
  subjects: SubjectUse[];
  sample_titles: string[];
  summary: string;
};

export type BilateralSupport = {
  bills: number;
  bipartisan_bills: number;
  share: number;
  bilateral: boolean;
  terms: TermUse[];
  subjects: SubjectUse[];
  sample_titles: string[];
  summary: string;
};

export type PartyShare = {
  party: PartyGroup;
  bills: number;
  share: number;
  lean: number;
};

export type Perspective = {
  label: string;
  size: number;
  terms: string[];
  sample_titles: string[];
  parties: PartyShare[];
};

export type PartyTopicDetail = {
  congress: number;
  topic_id: number;
  topic_label: string;
  bills: number;
  silhouette: number | null;
  stability: number | null;
  passed: boolean;
  party_terms: PartyTerms[];
  bilateral: BilateralSupport | null;
  perspectives: Perspective[];
  skipped_reason: string;
};

export type PartyTopicResponse = {
  topic: PartyTopicDetail;
};

export function fetchParties(congress?: number): Promise<PartiesResponse> {
  const query = congress === undefined ? '' : `?congress=${congress}`;
  return apiGet<PartiesResponse>(`/api/v1/parties${query}`);
}

export function fetchPartyTopic(congress: number, topicId: number): Promise<PartyTopicResponse> {
  return apiGet<PartyTopicResponse>(`/api/v1/parties/topics/${topicId}?congress=${congress}`);
}
