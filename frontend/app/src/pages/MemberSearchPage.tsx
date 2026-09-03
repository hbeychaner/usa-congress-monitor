import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchMembers, type MemberFilters, type MemberSummary } from '../api/members';

const PAGE_SIZE = 50;

export function MemberSearchPage() {
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<MemberFilters>({});
  const [draft, setDraft] = useState<MemberFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchMembers(page, PAGE_SIZE, filters).then((response) => {
      if (cancelled) return;
      setMembers(response.members);
      setTotal(response.total);
      setError(null);
    }).catch((err: Error) => {
      if (!cancelled) setError(err.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [page, filters]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  }

  return (
    <section>
      <header className="list-header"><div><p className="eyebrow">People directory</p><h1>Members</h1><p>Find current and historical members by identity, state, chamber, or party.</p></div><span className="result-count">{loading ? 'Loading' : `${total.toLocaleString()} records`}</span></header>
      <form className="member-filters" onSubmit={onSubmit}>
        <label className="filter-search">Search<input className="search-input" value={draft.query ?? ''} onChange={(event) => setDraft({ ...draft, query: event.target.value })} placeholder="Name, state, or Bioguide ID" /></label>
        <label>State<input className="filter-input" value={draft.state ?? ''} onChange={(event) => setDraft({ ...draft, state: event.target.value })} placeholder="South Dakota" /></label>
        <label>Chamber<select className="filter-input" value={draft.chamber ?? ''} onChange={(event) => setDraft({ ...draft, chamber: event.target.value })}><option value="">All chambers</option><option value="House">House</option><option value="Senate">Senate</option></select></label>
        <label>Party<select className="filter-input" value={draft.party ?? ''} onChange={(event) => setDraft({ ...draft, party: event.target.value })}><option value="">All parties</option><option value="Democratic">Democratic</option><option value="Republican">Republican</option><option value="Independent">Independent</option></select></label>
        <button className="button" type="submit">Apply filters</button>
      </form>
      {error ? <div className="panel"><p>Unable to load members: {error}</p></div> : null}
      {!loading && !error && members.length === 0 ? <div className="panel"><p>No members match these filters.</p></div> : null}
      {members.length > 0 ? <div className="table-shell"><table className="data-table member-table"><thead><tr><th scope="col">Member</th><th scope="col">Party</th><th scope="col">State</th><th scope="col">Chamber</th><th scope="col">District</th><th scope="col">Term</th></tr></thead><tbody>{members.map((member) => <tr key={member.bioguide_id}><th scope="row"><Link to={`/members/${encodeURIComponent(member.bioguide_id)}`}>{member.display_name}</Link><small>{member.bioguide_id}</small></th><td>{member.party}</td><td>{member.state}</td><td>{member.chamber ?? 'Not recorded'}</td><td>{member.district ?? 'At-large / not recorded'}</td><td>{member.term_start_year ?? 'Not recorded'}–{member.term_end_year ?? 'present'}</td></tr>)}</tbody></table></div> : null}
      <nav className="table-pagination" aria-label="Member pages"><button className="button button-secondary" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page} of {pageCount}</span><button className="button" disabled={page >= pageCount || loading} onClick={() => setPage(page + 1)}>Next</button></nav>
    </section>
  );
}
