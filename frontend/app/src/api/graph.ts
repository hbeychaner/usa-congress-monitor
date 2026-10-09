import { apiGet } from './client';
import type { components } from '../shared/contracts/api';

export type Neighborhood = components['schemas']['NeighborhoodResponse'];
export type GraphNode = components['schemas']['GraphNode'];
export type GraphLink = components['schemas']['GraphLink'];
export type PartyGroup = components['schemas']['PartyGroup'];

export type NeighborhoodParams = {
    members: string[];
    collaborationWeight: number;
    votingWeight: number;
    topicWeight: number;
    congress: number | null;
    chamber: 'house' | 'senate' | null;
    parties: PartyGroup[];
    limit: number;
    includeTopics: boolean;
};

export function fetchNeighborhood(params: NeighborhoodParams): Promise<Neighborhood> {
    const query = new URLSearchParams({
        collaboration_weight: String(params.collaborationWeight),
        voting_weight: String(params.votingWeight),
        topic_weight: String(params.topicWeight),
        limit: String(params.limit),
        include_topics: String(params.includeTopics),
    });
    params.members.forEach((member) => query.append('member', member));
    params.parties.forEach((party) => query.append('party', party));
    if (params.congress) query.set('congress', String(params.congress));
    if (params.chamber) query.set('chamber', params.chamber);
    return apiGet<Neighborhood>(`/api/v1/graph/neighborhood?${query.toString()}`);
}
