import { apiGet } from './client';

import type { PartyGroup } from './graph';

export type VotePosition = 'yea' | 'nay' | 'present' | 'not_voting';

export type VoteMember = {
  bioguide_id: string;
  name: string;
  state: string | null;
};

export type PositionMembers = {
  position: VotePosition;
  members: VoteMember[];
};

export type PartyVoteBreakdown = {
  party: PartyGroup;
  positions: PositionMembers[];
};

export type VoteBreakdownResponse = {
  vote_id: string;
  parties: PartyVoteBreakdown[];
};

export function fetchVoteBreakdown(rollcallId: string): Promise<VoteBreakdownResponse> {
  return apiGet<VoteBreakdownResponse>(`/api/v1/votes/${encodeURIComponent(rollcallId)}/breakdown`);
}
