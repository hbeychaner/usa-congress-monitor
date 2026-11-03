import type { BillFilters } from '../api/bills';
import type { MemberFilters } from '../api/members';
import type { SearchParams } from '../api/search';

export const BILL_TYPES = ['hr', 's', 'hres', 'sres', 'hjres', 'sjres', 'hconres', 'sconres'] as const;
export const SEARCH_TYPES = ['member', 'state', 'bill'] as const;
export type SearchKind = typeof SEARCH_TYPES[number];
export type BillQuery = BillFilters & { page: number };
export type MemberQuery = MemberFilters & { page: number };
export type SearchQuery = Omit<SearchParams, 'types'> & { types: SearchKind[] };
export interface QueryCodec<T> {
  read(params: URLSearchParams): { value: T; error: Error | null };
  write(value: T): URLSearchParams;
}

class QueryReader {
  error: Error | null = null;
  constructor(private readonly params: URLSearchParams) {}

  private invalid(name: string) {
    this.error ??= new Error(`Invalid URL parameter '${name}'. Correct the address or apply the filters again.`);
  }

  text(name: string): string | undefined {
    const values = this.params.getAll(name);
    if (values.length > 1) this.invalid(name);
    return values[0] || undefined;
  }

  integer(name: string, fallback: number, max = Number.MAX_SAFE_INTEGER): number {
    const raw = this.text(name);
    if (raw === undefined && !this.params.has(name)) return fallback;
    const value = Number(raw);
    if (!raw || !/^\d+$/.test(raw) || !Number.isSafeInteger(value) || value < 1 || value > max) {
      this.invalid(name);
      return fallback;
    }
    return value;
  }

  option<T extends string>(name: string, choices: readonly T[]): T | undefined {
    const raw = this.text(name);
    if (!raw) return undefined;
    const value = choices.find(choice => choice.toLowerCase() === raw.toLowerCase());
    if (!value) this.invalid(name);
    return value;
  }

  boolean(name: string): boolean {
    const raw = this.text(name)?.toLowerCase();
    if (raw === undefined) {
      if (this.params.has(name)) this.invalid(name);
      return false;
    }
    if (['true', '1', 'yes', 'on'].includes(raw)) return true;
    if (!['false', '0', 'no', 'off'].includes(raw)) this.invalid(name);
    return false;
  }

  types(): SearchKind[] {
    const raw = this.text('types');
    const tokens = raw?.split(',').map(value => value.trim().toLowerCase()).filter(Boolean) ?? [];
    if (tokens.some(value => !SEARCH_TYPES.some(type => type === value))) this.invalid('types');
    return tokens.length ? SEARCH_TYPES.filter(type => tokens.includes(type)) : [...SEARCH_TYPES];
  }
}

function encode(values: Record<string, string | number | boolean | undefined>): URLSearchParams {
  return new URLSearchParams(Object.entries(values)
    .filter(([, value]) => value !== undefined && value !== '' && value !== false)
    .map(([name, value]) => [name, String(value)]));
}

export const billQuery: QueryCodec<BillQuery> = {
  read(params) {
    const reader = new QueryReader(params);
    return { value: {
      page: reader.integer('page', 1), query: reader.text('query'),
      congress: reader.text('congress'), chamber: reader.option('chamber', ['House', 'Senate']),
      billType: reader.option('bill_type', BILL_TYPES), subject: reader.text('subject'),
      hasVotes: reader.boolean('has_votes'),
    }, error: reader.error };
  },
  write(value) {
    return encode({ query: value.query, congress: value.congress, chamber: value.chamber,
      bill_type: value.billType, subject: value.subject, has_votes: value.hasVotes,
      page: value.page === 1 ? undefined : value.page });
  },
};

export const memberQuery: QueryCodec<MemberQuery> = {
  read(params) {
    const reader = new QueryReader(params);
    return { value: {
      page: reader.integer('page', 1), query: reader.text('query'), state: reader.text('state'),
      chamber: reader.option('chamber', ['House', 'Senate']), party: reader.text('party'),
    }, error: reader.error };
  },
  write(value) {
    return encode({ query: value.query, state: value.state, chamber: value.chamber, party: value.party,
      page: value.page === 1 ? undefined : value.page });
  },
};

export const searchQuery: QueryCodec<SearchQuery> = {
  read(params) {
    const reader = new QueryReader(params);
    return { value: {
      query: reader.text('q') ?? '', types: reader.types(), limit: reader.integer('limit', 20, 100),
    }, error: reader.error };
  },
  write(value) {
    const types = SEARCH_TYPES.filter(type => value.types.includes(type));
    return encode({ q: value.query, types: !types.length || types.length === SEARCH_TYPES.length ? undefined : types.join(','),
      limit: value.limit === 20 ? undefined : value.limit });
  },
};
