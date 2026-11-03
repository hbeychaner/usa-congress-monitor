import { expect, test as base, type BrowserContext, type Route } from '@playwright/test';
import type * as Contracts from '../../src/shared/contracts/api';

type Handler = (route: Route, url: URL) => Promise<void>;

export const billId = 'bill:119:hr:1';
export const memberId = 'A000001';
export const unavailable = {
  detail: 'Analysis is unavailable. Please try again later.',
  analysis_state: 'unavailable',
} satisfies Contracts.AnalysisErrorResponse;
const notBuilt: Contracts.AnalysisStatus = {
  state: 'not_built', published_model_version: null, source_model_version: null,
};
const member: Contracts.MemberDetail = {
  bioguide_id: memberId, display_name: 'Alex Fixture', party: 'Independent', state: 'California',
  chamber: 'House', district: 1, birth_year: null, death_year: null, current_member: true,
  honorific_name: null, image_attribution: null, image_url: null, leadership: [],
  office_address: null, official_website_url: null, party_history: [], phone_number: null,
  term_start_year: 2025, term_end_year: null, terms: [],
};
export const bill: Contracts.BillDetail = {
  bill_id: billId, title: 'Fixture Health Bill', bill_type: 'hr', number: '1', congress: 119,
  actions: [], committees: [], constitutional_authority_statement_text: null,
  cosponsors: [], full_text: null, full_text_version_code: null, introduced_date: null,
  latest_action: null, laws: [], origin_chamber: 'House', origin_chamber_code: 'H',
  policy_area: 'Health', related_bills: [], relationship_counts: {}, sponsors: [],
  subjects: null, summaries: [], text_versions: [], titles: [], update_date: null,
  update_date_including_text: null,
  hydration: {
    schema_version: 1, status: 'unknown', source: 'unknown', assessed_at: null,
    details: {}, reason: 'No versioned bill-detail hydration evidence is available.',
  },
};
const timelineMember: Contracts.TimelineMember = {
  bioguide_id: memberId, name: member.display_name, party: member.party,
  congress_start: 119, congress_end: 119,
};

function bounds(page: number, limit: number, total = 150) {
  return {
    page, limit, total, max_page: Math.max(1, Math.min(Math.ceil(total / limit), Math.floor(10_000 / limit))),
    max_result_window: 10_000, window_limited: total > Math.floor(10_000 / limit) * limit,
  };
}

export function bills(url: URL): Contracts.BillsResponse {
  const query = url.searchParams.get('query') ?? 'all';
  return {
    ...bounds(Number(url.searchParams.get('page') ?? 1), 50, query === 'window' ? 10_001 : 150),
    bills: [{
      bill_id: billId, title: `${query} bill`, bill_type: 'hr', number: '1',
      chamber: 'House', congress: 119, updated_at: null, vote_count: 0,
    }],
  };
}

export class ApiFixture {
  readonly requests: URL[] = [];
  readonly unexpectedRequests: string[] = [];
  private readonly handlers = new Map<string, Handler>();

  constructor(private readonly context: BrowserContext, private readonly appOrigin: string) {}

  async attach(): Promise<void> {
    await this.context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin === 'http://127.0.0.1:8000' && request.method() === 'GET') {
        this.requests.push(url);
        const handler = this.handlers.get(url.pathname);
        if (handler) {
          await handler(route, url);
          return;
        }
        if (await this.respond(route, url)) return;
      } else if (url.origin === this.appOrigin && request.method() === 'GET'
        && !url.pathname.startsWith('/api/') && url.pathname !== '/ready'
        && ['document', 'script', 'stylesheet', 'image', 'font', 'manifest'].includes(request.resourceType())) {
        await route.continue();
        return;
      }
      this.unexpectedRequests.push(`${request.method()} ${url.href}`);
      await route.abort('blockedbyclient');
    });
  }

  override(path: string, handler: Handler): void {
    this.handlers.set(path, handler);
  }

  count(path: string): number {
    return this.requests.filter(url => url.pathname === path).length;
  }

  last(path: string): URL {
    const request = this.requests.filter(url => url.pathname === path).pop();
    if (!request) throw new Error(`No fixture API request for ${path}`);
    return request;
  }

  verify(): void {
    expect(this.unexpectedRequests, 'Unexpected API/external traffic').toEqual([]);
  }

  async respond(route: Route, url: URL): Promise<boolean> {
    const path = decodeURIComponent(url.pathname);
    if (path === '/ready') {
      await route.fulfill({ json: { status: 'ready' } satisfies Contracts.ReadinessResponse });
    } else if (path === '/api/v1/bills/recent') {
      await route.fulfill({ json: bills(url) });
    } else if (path === '/api/v1/members') {
      await route.fulfill({ json: {
        ...bounds(Number(url.searchParams.get('page') ?? 1), 50), members: [member],
      } satisfies Contracts.MembersResponse });
    } else if (path === '/api/v1/search') {
      const query = url.searchParams.get('q') ?? '';
      const types = (url.searchParams.get('types') ?? 'member,state,bill').split(',');
      await route.fulfill({ json: {
        query, types, limit: Number(url.searchParams.get('limit') ?? 20), ordering: 'grouped',
        results: query === 'empty' ? [] : types.map(result_type => ({
          result_type, id: result_type === 'bill' ? billId : result_type === 'member' ? memberId : 'CA',
          title: `${query} ${result_type}`, subtitle: null,
        })),
      } satisfies Contracts.SearchResponse });
    } else if (path === '/api/v1/states/CA/timeline') {
      await route.fulfill({ json: {
        state_code: 'CA', state_name: 'California',
        house: { chamber: 'House', members: [timelineMember], groups: [{ congress: 119, members: [timelineMember] }] },
        senate: { chamber: 'Senate', members: [], groups: [] },
      } satisfies Contracts.StateTimelineResponse });
    } else if (path === `/api/v1/members/${memberId}`) {
      await route.fulfill({ json: {
        member, recent_activity: [{ bill_id: billId, title: bill.title, congress: 119, activity_type: 'sponsored' }],
      } satisfies Contracts.MemberProfileResponse });
    } else if (path === `/api/v1/members/${memberId}/topics`) {
      await route.fulfill({ json: {
        bioguide_id: memberId, analysis: notBuilt, model_version: null,
        topics: [], trend: [], subjects: [], policy_areas: [],
      } satisfies Contracts.MemberTopicsResponse });
    } else if (path === `/api/v1/members/${memberId}/activity`) {
      await route.fulfill({ json: {
        ...bounds(Number(url.searchParams.get('page') ?? 1), 25, 1),
        counts: { bill: 1 }, items: [{
          id: billId, bill_id: billId, title: bill.title, document_type: 'bill',
          activity_type: 'sponsored', congress: 119, date: '2025-01-03',
        }],
      } satisfies Contracts.MemberActivityResponse });
    } else if (path === `/api/v1/bills/${billId}`) {
      await route.fulfill({ json: { bill } satisfies Contracts.BillDetailResponse });
    } else if (path === `/api/v1/bills/${billId}/votes`) {
      await route.fulfill({ json: { bill_id: billId, votes: [], total: 0 } satisfies Contracts.BillVotesResponse });
    } else if (path === `/api/v1/bills/${billId}/topics`) {
      await route.fulfill({ json: {
        bill_id: billId, topics: [], model_version: null, analysis: notBuilt,
      } satisfies Contracts.BillTopicsResponse });
    } else if (path === `/api/v1/bills/${billId}/similar`) {
      await route.fulfill({ json: {
        bill_id: billId, similar: [], analysis: notBuilt,
      } satisfies Contracts.SimilarBillsResponse });
    } else {
      return false;
    }
    return true;
  }
}

export const test = base.extend<{ api: ApiFixture }>({
  api: [async ({ context, page, baseURL }, use) => {
    if (!baseURL) throw new Error('Browser fixtures require the configured preview origin.');
    const api = new ApiFixture(context, baseURL);
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await api.attach();
    await use(api);
    api.verify();
    expect(errors, 'Uncaught browser errors').toEqual([]);
  }, { auto: true }],
});

export { expect } from '@playwright/test';
