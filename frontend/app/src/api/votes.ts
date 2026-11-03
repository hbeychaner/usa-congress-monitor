import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type VotePosition = Contracts.VotePosition;
export type VoteMember = Contracts.VoteMember;
export type PositionMembers = Contracts.PositionMembers;
export type PartyVoteBreakdown = Contracts.PartyVoteBreakdown;
export type VoteBreakdownResponse = Contracts.VoteBreakdownResponse;

export function fetchVoteBreakdown(rollcallId: string): Promise<VoteBreakdownResponse> {
  return apiGet<VoteBreakdownResponse>(`/api/v1/votes/${encodeURIComponent(rollcallId)}/breakdown`);
}
