import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchBill, type BillDetailResponse } from '../api/bills';

type RecordValue = Record<string, unknown>;

function formatDate(value: string | null | undefined): string {
    if (!value) return 'Not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function displayName(sponsor: RecordValue): string {
    return String(sponsor.full_name ?? sponsor.name ?? sponsor.id ?? 'Unknown sponsor');
}

export function BillDetailPage() {
    const { billId = '' } = useParams();
    const [response, setResponse] = useState<BillDetailResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setResponse(null);
        setError(null);
        fetchBill(billId).then(setResponse).catch((err: Error) => setError(err.message));
    }, [billId]);

    if (error) return <section className="panel"><h1>Bill unavailable</h1><p>{error}</p><Link to="/bills">Back to bills</Link></section>;
    if (!response) return <section className="panel"><p>Loading bill...</p></section>;

    const bill = response.bill;
    const action = bill.latest_action as RecordValue | null;
    const subjects = bill.subjects?.legislativeSubjects;
    const sponsors = bill.sponsors ?? [];
    const relationshipCounts = bill.relationship_counts ?? {};

    return (
        <section className="bill-detail-page">
            <Link to="/bills" className="back-link">Back to bills</Link>
            <header className="bill-hero">
                <div>
                    <p className="eyebrow">{bill.bill_type ?? 'Bill'} {bill.number ?? ''} · Congress {bill.congress ?? 'Unknown'}</p>
                    <h1>{bill.title}</h1>
                    <p className="bill-deck">{bill.origin_chamber ?? 'Chamber not recorded'} · Introduced {formatDate(bill.introduced_date)}</p>
                </div>
                <a className="button" href={`https://www.congress.gov/bill/${bill.congress}/${(bill.bill_type ?? '').toLowerCase()}/${bill.number}`} target="_blank" rel="noreferrer">View on Congress.gov</a>
            </header>

            <div className="bill-detail-grid">
                <div className="bill-main-column">
                    <section className="panel">
                        <h2>Latest action</h2>
                        {action ? <div className="action-callout"><strong>{formatDate(String(action.action_date ?? ''))}</strong><span>{String(action.text ?? 'Action text not recorded')}</span></div> : <p>No action is recorded for this bill.</p>}
                    </section>
                    <section className="panel">
                        <h2>Policy and subjects</h2>
                        {bill.policy_area ? <p className="chip-row"><span className="chip">{bill.policy_area}</span></p> : <p>Policy area not recorded.</p>}
                        {Array.isArray(subjects) && subjects.length > 0 ? <ul className="detail-list">{subjects.map((subject, index) => <li key={`${String(subject.name ?? subject.title ?? index)}`}>{String(subject.name ?? subject.title ?? 'Unnamed subject')}</li>)}</ul> : <p>Legislative subjects are not expanded in this record.</p>}
                    </section>
                    {bill.full_text ? <details className="panel bill-text"><summary>Bill text</summary><pre>{bill.full_text}</pre></details> : null}
                </div>

                <aside className="bill-sidebar">
                    <section className="panel"><h2>Bill record</h2><dl className="metadata-list"><dt>Type</dt><dd>{bill.bill_type ?? 'Not recorded'}</dd><dt>Number</dt><dd>{bill.number ?? 'Not recorded'}</dd><dt>Origin chamber</dt><dd>{bill.origin_chamber ?? 'Not recorded'}</dd><dt>Last updated</dt><dd>{formatDate(bill.update_date)}</dd></dl></section>
                    <section className="panel"><h2>Sponsors</h2>{sponsors.length ? <ul className="detail-list">{sponsors.map((sponsor) => <li key={String(sponsor.id ?? displayName(sponsor))}><strong>{displayName(sponsor)}</strong>{sponsor.party || sponsor.state ? <span>{[sponsor.party, sponsor.state, sponsor.district ? `District ${sponsor.district}` : ''].filter(Boolean).join(' · ')}</span> : null}</li>)}</ul> : <p>No sponsors are indexed for this bill.</p>}</section>
                    <section className="panel"><h2>Available records</h2>{Object.keys(relationshipCounts).length ? <ul className="metadata-list">{Object.entries(relationshipCounts).map(([name, count]) => <li key={name}><span>{name.replace(/_/g, ' ')}</span><strong>{count}</strong></li>)}</ul> : <p>No related record counts are available.</p>}</section>
                </aside>
            </div>
        </section>
    );
}
