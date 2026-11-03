import { apiGet } from './client';
import type * as Contracts from '../shared/contracts/api';

export type Neighborhood = Contracts.NeighborhoodResponse;
export type GraphNode = Contracts.GraphNode;
export type GraphLink = Contracts.GraphLink;
export type PartyGroup = Contracts.PartyGroup;

export type NeighborhoodParams = {
    members: string[];
    collaborationWeight: number;
    votingWeight: number;
    topicWeight: number;
    congress: number | null;
    chamber: Contracts.Chamber | null;
    parties: PartyGroup[];
    limit: number;
    includeTopics: boolean;
    includeSubjects: boolean;
    includeMetasubjects: boolean;
};

export function fetchNeighborhood(params: NeighborhoodParams): Promise<Neighborhood> {
    const query = new URLSearchParams({
        collaboration_weight: String(params.collaborationWeight),
        voting_weight: String(params.votingWeight),
        topic_weight: String(params.topicWeight),
        limit: String(params.limit),
        include_topics: String(params.includeTopics),
        include_subjects: String(params.includeSubjects),
        include_metasubjects: String(params.includeMetasubjects),
    });
    params.members.forEach((member) => query.append('member', member));
    params.parties.forEach((party) => query.append('party', party));
    if (params.congress) query.set('congress', String(params.congress));
    if (params.chamber) query.set('chamber', params.chamber);
    return apiGet<Neighborhood>(`/api/v1/graph/neighborhood?${query.toString()}`);
}

export type CenterKind = Contracts.CenterKind;

export type TopicNeighborhoodParams = Omit<
    NeighborhoodParams,
    'members' | 'includeTopics' | 'includeSubjects' | 'includeMetasubjects'
> & { kind: CenterKind; key: string };

export function fetchTopicNeighborhood(params: TopicNeighborhoodParams): Promise<Neighborhood> {
    const query = new URLSearchParams({
        kind: params.kind,
        key: params.key,
        collaboration_weight: String(params.collaborationWeight),
        voting_weight: String(params.votingWeight),
        topic_weight: String(params.topicWeight),
        limit: String(params.limit),
    });
    params.parties.forEach((party) => query.append('party', party));
    if (params.congress) query.set('congress', String(params.congress));
    if (params.chamber) query.set('chamber', params.chamber);
    return apiGet<Neighborhood>(`/api/v1/graph/topic-neighborhood?${query.toString()}`);
}
