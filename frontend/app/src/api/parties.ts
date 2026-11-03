import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type PartyTopicEntry = Contracts.PartyTopicEntry;
export type PartyRanking = Contracts.PartyRanking;
export type BilateralTopicEntry = Contracts.BilateralTopicEntry;
export type PartiesResponse = Contracts.PartiesResponse;
export type BillRef = Contracts.BillRef;
export type TermUse = Contracts.TermUse;
export type SubjectUse = Contracts.SubjectUse;
export type PartyTerms = Contracts.PartyTerms;
export type BilateralSupport = Contracts.BilateralSupport;
export type PartyShare = Contracts.PartyShare;
export type Perspective = Contracts.Perspective;
export type PartyTopicDetail = Contracts.TopicPerspectives;
export type PartyTopicResponse = Contracts.PartyTopicResponse;

export function fetchParties(congress?: number): Promise<PartiesResponse> {
  const query = congress === undefined ? '' : `?congress=${congress}`;
  return apiGet<PartiesResponse>(`/api/v1/parties${query}`);
}

export function fetchPartyTopic(congress: number, topicId: number): Promise<PartyTopicResponse> {
  return apiGet<PartyTopicResponse>(`/api/v1/parties/topics/${topicId}?congress=${congress}`);
}
