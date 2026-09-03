import { useEffect, useMemo, useRef, useState } from 'react';

import { fetchAdminIngestSnapshot, fetchIngestProgress, type AdminIngestSnapshot, type IngestProgressResponse } from '../api/admin';

function formatPct(done: number, total: number): string {
    if (total <= 0) {
        return '0.0';
    }
    return ((done / total) * 100).toFixed(1);
}

function formatDuration(seconds: number): string {
    const roundedSeconds = Math.max(0, Math.round(seconds));
    const days = Math.floor(roundedSeconds / 86400);
    const hours = Math.floor((roundedSeconds % 86400) / 3600);
    const minutes = Math.floor((roundedSeconds % 3600) / 60);

    if (days > 0) {
        return `${days}d ${hours}h`;
    }
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${Math.max(1, minutes)}m`;
}

function formatDate(date: string | null): string {
    if (!date) {
        return 'n/a';
    }
    return date;
}

export function AdminIngestPage() {
    const [data, setData] = useState<IngestProgressResponse | null>(null);
    const [snapshot, setSnapshot] = useState<AdminIngestSnapshot | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [statusFilter, setStatusFilter] = useState('');

    const previousHydratedRef = useRef<number | null>(null);
    const previousDiscoveredRef = useRef<number | null>(null);
    const previousAtRef = useRef<number | null>(null);
    const [hydrationRate, setHydrationRate] = useState<number | null>(null);
    const [discoveryRate, setDiscoveryRate] = useState<number | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                const [progress, status] = await Promise.all([
                    fetchIngestProgress(),
                    fetchAdminIngestSnapshot(),
                ]);
                if (cancelled) {
                    return;
                }

                const now = Date.now();
                if (
                    previousAtRef.current !== null &&
                    previousHydratedRef.current !== null &&
                    previousDiscoveredRef.current !== null &&
                    now > previousAtRef.current
                ) {
                    const elapsed = (now - previousAtRef.current) / 1000;
                    setHydrationRate(Math.max(0, (progress.hydrated - previousHydratedRef.current) / elapsed));
                    setDiscoveryRate(Math.max(0, (progress.discovered - previousDiscoveredRef.current) / elapsed));
                }

                previousAtRef.current = now;
                previousHydratedRef.current = progress.hydrated;
                previousDiscoveredRef.current = progress.discovered;
                setData(progress);
                setSnapshot(status);
                setLastUpdated(new Date(now));
                setError(null);
            } catch (err) {
                if (!cancelled) {
                    setError((err as Error).message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        load();
        const timer = window.setInterval(load, 10000);

        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, []);

    const totals = useMemo(() => {
        if (!data) {
            return null;
        }
        return {
            hydratedPct: formatPct(data.hydrated, data.target),
            discoveredPct: formatPct(data.discovered, data.target),
        };
    }, [data]);

    const filteredJobs = useMemo(() => {
        if (!data || !statusFilter) {
            return data?.jobs ?? [];
        }
        return data.jobs.filter((job) => job.status === statusFilter);
    }, [data, statusFilter]);

    const completionEta = useMemo(() => {
        if (!data || data.remaining === 0) {
            return data ? 'Complete' : 'Calculating';
        }
        if (hydrationRate === null || hydrationRate <= 0) {
            return 'Calculating';
        }
        return `About ${formatDuration(data.remaining / hydrationRate)}`;
    }, [data, hydrationRate]);

    return (
        <section className="admin-page">
            <h1>Ingest Admin</h1>
            <p>Live acquisition and indexing state. Auto-refreshes every 10 seconds.</p>

            <div className="panel admin-status-row">
                <div>
                    <strong>Last updated:</strong> {lastUpdated ? lastUpdated.toLocaleTimeString() : 'n/a'}
                </div>
                <div>
                    <strong>Active jobs:</strong> {data?.active_jobs ?? 0}
                </div>
            </div>

            {error ? <div className="panel"><p>Failed to load progress: {error}</p></div> : null}

            {loading && !data ? (
                <div className="panel"><p>Loading ingest progress...</p></div>
            ) : null}

            {data && totals ? (
                <>
                    {snapshot ? (
                        <div className="admin-overview-grid">
                            <div className={`panel readiness-panel ${snapshot.ready_for_reconciliation ? 'is-ready' : 'is-blocked'}`}>
                                <span className="eyebrow">118th Congress</span>
                                <h2>{snapshot.ready_for_reconciliation ? 'Ready for reconciliation' : 'Acquisition in progress'}</h2>
                                <p>{snapshot.govinfo.pending.toLocaleString()} packages remain before the complete-coverage gate opens.</p>
                            </div>
                            <div className="panel metric-panel">
                                <span className="eyebrow">GovInfo coverage</span>
                                <strong>{snapshot.govinfo.available.toLocaleString()} / {snapshot.govinfo.expected.toLocaleString()}</strong>
                                <span>{snapshot.govinfo.failed + snapshot.govinfo.not_available} classified gaps · {snapshot.govinfo.pending.toLocaleString()} pending</span>
                            </div>
                            <div className="panel metric-panel">
                                <span className="eyebrow">Staging index</span>
                                <strong>{snapshot.staging.documents.toLocaleString()} documents</strong>
                                <span>{snapshot.staging.exists ? snapshot.staging.index : 'Not created'} · {snapshot.staging.connected ? 'OpenSearch connected' : 'OpenSearch unavailable'}</span>
                            </div>
                        </div>
                    ) : null}

                    {snapshot ? (
                        <div className="panel admin-coverage">
                            <h2>Pipeline Status</h2>
                            <div className="status-grid">
                                <div><span>GovInfo packages</span><strong>{snapshot.govinfo_jobs.queued.toLocaleString()} queued · {snapshot.govinfo_jobs.running} running</strong></div>
                                <div><span>GovInfo batches</span><strong>{snapshot.govinfo_batch_jobs.queued.toLocaleString()} queued · {snapshot.govinfo_batch_jobs.running} running</strong></div>
                                <div><span>Index jobs</span><strong>{snapshot.index_jobs.queued.toLocaleString()} queued · {snapshot.index_jobs.failed} failed</strong></div>
                                <div><span>Reconciliation</span><strong>{snapshot.reconcile_jobs.succeeded} complete · {snapshot.reconcile_jobs.running} running</strong></div>
                                <div><span>Production read alias</span><strong>{snapshot.staging.production_alias_target ?? 'Unavailable'}</strong></div>
                            </div>
                        </div>
                    ) : null}

                    <div className="panel admin-bars">
                        <h2>Aggregate Progress</h2>
                        <div className="progress-row">
                            <div className="progress-label">Hydrated</div>
                            <div className="progress-track" role="progressbar" aria-label="Hydration completion" aria-valuemin={0} aria-valuemax={data.target} aria-valuenow={data.hydrated}>
                                <div className="progress-fill progress-fill-hydrated" style={{ width: `${Math.min(100, Number(totals.hydratedPct))}%` }} />
                            </div>
                            <div className="progress-metric">{data.hydrated.toLocaleString()} / {data.target.toLocaleString()} ({totals.hydratedPct}%)</div>
                        </div>

                        <div className="progress-row">
                            <div className="progress-label">Discovered</div>
                            <div className="progress-track" role="progressbar" aria-label="Discovery completion" aria-valuemin={0} aria-valuemax={data.target} aria-valuenow={data.discovered}>
                                <div className="progress-fill progress-fill-discovered" style={{ width: `${Math.min(100, Number(totals.discoveredPct))}%` }} />
                            </div>
                            <div className="progress-metric">{data.discovered.toLocaleString()} / {data.target.toLocaleString()} ({totals.discoveredPct}%)</div>
                        </div>

                        <p>
                            Remaining to hydrate: <strong>{data.remaining.toLocaleString()}</strong>
                            {' · '}
                            Hydration rate: <strong>{hydrationRate === null ? 'n/a' : `${hydrationRate.toFixed(2)} rec/s`}</strong>
                            {' · '}
                            Discovery rate: <strong>{discoveryRate === null ? 'n/a' : `${discoveryRate.toFixed(2)} rec/s`}</strong>
                            {' · '}
                            Estimated completion: <strong>{completionEta}</strong>
                        </p>
                    </div>

                    <div className="panel">
                        <div className="admin-table-header">
                            <h2>Per Job</h2>
                            <label>
                                Status
                                <select className="filter-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                                    <option value="">All statuses</option>
                                    <option value="queued">Queued</option>
                                    <option value="running">Running</option>
                                    <option value="retrying">Retrying</option>
                                </select>
                            </label>
                        </div>
                        {data.jobs.length > 0 ? <p className="table-result-count">Showing {filteredJobs.length.toLocaleString()} of {data.jobs.length.toLocaleString()} active jobs</p> : null}
                        {data.jobs.length === 0 ? (
                            <p>No active ingest jobs.</p>
                        ) : filteredJobs.length === 0 ? (
                            <p>No active jobs match this status.</p>
                        ) : (
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>Job</th>
                                        <th>Status</th>
                                        <th>Resource</th>
                                        <th>Window</th>
                                        <th>Hydrated</th>
                                        <th>Discovered</th>
                                        <th>Target</th>
                                        <th>Remaining</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredJobs.map((job) => (
                                        <tr key={job.job_id}>
                                            <td>{job.job_id.replace('ingest:', '').slice(0, 10)}</td>
                                            <td>{job.status}</td>
                                            <td>{job.resource}</td>
                                            <td>{formatDate(job.from_date)} to {formatDate(job.to_date)}</td>
                                            <td>{job.hydrated.toLocaleString()}</td>
                                            <td>{job.discovered.toLocaleString()}</td>
                                            <td>{job.target.toLocaleString()}</td>
                                            <td>{job.remaining.toLocaleString()}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </>
            ) : null}
        </section>
    );
}
