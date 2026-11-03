import type * as Contracts from '../src/shared/contracts/api';
import type { BillSummary, BillsResponse, SimilarBillsResponse } from '../src/api/bills';
import type { MemberGraphStatus, TopicTrainingStatus } from '../src/api/admin';
import type { PartiesResponse, PartyTopicDetail } from '../src/api/parties';
import type { TopicsResponse, MemberTopicsResponse } from '../src/api/topics';
import type { VotePosition } from '../src/api/votes';
import type { AnalysisState, AnalysisStatus } from '../src/api/analysis';
import type { MemberProfileResponse, MemberActivityResponse, MembersResponse } from '../src/api/members';
import type { SearchResponse } from '../src/api/search';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends
    (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;

type WrapperSchemasMatch = Assert<Equal<
    [BillSummary, BillsResponse, SimilarBillsResponse, MemberGraphStatus,
        TopicTrainingStatus, PartiesResponse, PartyTopicDetail, TopicsResponse,
        MemberTopicsResponse],
    [Contracts.BillSummary, Contracts.BillsResponse,
        Contracts.SimilarBillsResponse, Contracts.GraphBuildStatus,
        Contracts.TopicTrainingStatus, Contracts.PartiesResponse,
        Contracts.TopicPerspectives, Contracts.TopicsResponse,
        Contracts.MemberTopicsResponse]
>>;
type BillNumbersAreNullableStrings = Assert<Equal<BillSummary['number'], string | null>>;
type DefaultListsArePresent = Assert<Equal<SimilarBillsResponse['similar'],
    Contracts.SimilarBill[]>>;
type NullableLineageIsPresent = Assert<Equal<TopicsResponse['model_version'], string | null>>;
type JobIdsAreNullableStrings = Assert<Equal<MemberGraphStatus['job_id'], string | null>>;
type PositionsMatch = Assert<Equal<VotePosition, 'yea' | 'nay' | 'present' | 'not_voting'>>;

type GraphQuery = Contracts.NeighborhoodApiV1GraphNeighborhoodGetData['query'];
const allCongresses: GraphQuery = { member: ['A'], congress: null, chamber: 'house' };
// @ts-expect-error Congress is numeric at the API boundary.
const invalidCongress: GraphQuery = { member: ['A'], congress: '119' };
// @ts-expect-error Chamber uses the generated closed enum.
const invalidChamber: GraphQuery = { member: ['A'], chamber: 'House' };
// @ts-expect-error Unknown vote positions are rejected.
const invalidPosition: VotePosition = 'maybe';

type AnalysisStatesAreClosed = Assert<Equal<AnalysisState,
    'available' | 'not_built' | 'empty' | 'stale' | 'unknown' | 'unavailable'>>;
type AnalysisIsAlwaysPresent = Assert<Equal<TopicsResponse['analysis'], AnalysisStatus>>;
type EmptyIsNotNull = Assert<Equal<MemberTopicsResponse['topics'], Contracts.TopicItem[]>>;
type ProfileDoesNotEmbedAnalysis = Assert<Equal<'topics' extends keyof MemberProfileResponse ? true : false, false>>;
type PageMetadata = { max_page: number; max_result_window: number; window_limited: boolean };
type ListingBoundsAreRequired = Assert<Equal<
    [BillsResponse, MembersResponse, MemberActivityResponse] extends [PageMetadata, PageMetadata, PageMetadata] ? true : false,
    true
>>;
type SearchOrderingIsGrouped = Assert<Equal<SearchResponse['ordering'], 'grouped'>>;
