import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchRecentBills, type BillFilters, type BillSummary } from '../api/bills';

const PAGE_SIZE = 50;
const BILL_TYPES = ['hr', 's', 'hres', 'sres', 'hjres', 'sjres', 'hconres', 'sconres'];

function label(bill: BillSummary): string {
  return [bill.bill_type?.toUpperCase(), bill.number].filter(Boolean).join(' ');
}

export function BillsPage() {
  const [bills, setBills] = useState<BillSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<BillFilters>({});
  const [draft, setDraft] = useState<BillFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchRecentBills(PAGE_SIZE, page, filters)
      .then((response) => {
        if (!cancelled) {
          setBills(response.bills);
          setTotal(response.total);
          setError(null);
        }
      })
      .catch((err: Error) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, filters]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  };

  return (
    <section className="bills-page">
      <header className="list-header"><div><p className="eyebrow">Legislation index</p><h1>Bills</h1><p>Browse {total.toLocaleString()} indexed bills with server-side search and filters.</p></div><span className="result-count">{loading ? 'Loading' : `${((page - 1) * PAGE_SIZE + (bills.length ? 1 : 0)).toLocaleString()}–${Math.min(page * PAGE_SIZE, total).toLocaleString()}`} of {total.toLocaleString()}</span></header>
      <form className="bill-filters" onSubmit={applyFilters}>
        <label className="filter-search">Search bills<input className="search-input" value={draft.query ?? ''} onChange={(event) => setDraft({ ...draft, query: event.target.value })} placeholder="Title, sponsor, policy area, or bill ID" /></label>
        <label>Congress<input className="filter-input" inputMode="numeric" value={draft.congress ?? ''} onChange={(event) => setDraft({ ...draft, congress: event.target.value })} placeholder="119" /></label>
        <label>Chamber<select className="filter-input" value={draft.chamber ?? ''} onChange={(event) => setDraft({ ...draft, chamber: event.target.value })}><option value="">All chambers</option><option value="House">House</option><option value="Senate">Senate</option></select></label>
        <label>Type<select className="filter-input" value={draft.billType ?? ''} onChange={(event) => setDraft({ ...draft, billType: event.target.value })}><option value="">All types</option>{BILL_TYPES.filter(Boolean).filter((type, index, list) => list.indexOf(type) === index).map((type) => <option key={type} value={type}>{type.toUpperCase()}</option>)}</select></label>
        <button className="button" type="submit">Apply filters</button>
      </form>
      {error ? <div className="panel"><p>Unable to load bills: {error}</p></div> : null}
      {!loading && !error && bills.length === 0 ? <div className="panel"><p>No bills match these filters.</p></div> : null}
      {bills.length > 0 ? <div className="table-shell"><table className="data-table"><thead><tr><th scope="col">Bill</th><th scope="col">Title</th><th scope="col">Congress</th><th scope="col">Chamber</th><th scope="col">Updated</th></tr></thead><tbody>{bills.map((bill) => <tr key={bill.bill_id}><th scope="row"><Link to={`/bills/${encodeURIComponent(bill.bill_id)}`}>{label(bill) || bill.bill_id}</Link></th><td className="title-cell">{bill.title}</td><td>{bill.congress ?? '—'}</td><td>{bill.chamber ?? '—'}</td><td>{bill.updated_at ? new Date(bill.updated_at).toLocaleDateString() : '—'}</td></tr>)}</tbody></table></div> : null}
      <nav className="table-pagination" aria-label="Bill pages"><button className="button button-secondary" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page} of {pageCount}</span><button className="button" disabled={page >= pageCount || loading} onClick={() => setPage(page + 1)}>Next</button></nav>
    </section>
  );
}
