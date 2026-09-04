import { useEffect, useMemo, useState } from 'react';

import { fetchAdminIngestSnapshot, fetchIngestProgress, type AdminIngestSnapshot, type IngestProgressResponse } from '../api/admin';

function formatPct(done: number, total: number): string {
    if (total <= 0) {
        return '0.0';
    }
    return ((done / total) * 100).toFixed(1);
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

    const pipelineProgress = useMemo(() => {
        if (!snapshot) {
            return null;
        }
        const packageJobs = snapshot.govinfo_jobs;
        const indexJobs = snapshot.index_jobs;
        const jobTotal = (jobs: typeof packageJobs) => Object.values(jobs).reduce((sum, count) => sum + count, 0);
        return {
            packages: { completed: packageJobs.succeeded, target: jobTotal(packageJobs), queued: packageJobs.queued, running: packageJobs.running },
            indexing: { completed: indexJobs.succeeded, target: jobTotal(indexJobs), queued: indexJobs.queued, running: indexJobs.running },
            coverage: { completed: snapshot.govinfo.available, target: snapshot.govinfo.expected, queued: snapshot.govinfo.pending, running: 0 },
        };
    }, [snapshot]);

    const filteredJobs = useMemo(() => {
        if (!data || !statusFilter) {
            return data?.jobs ?? [];
        }
        return data.jobs.filter((job) => job.status === statusFilter);
    }, [data, statusFilter]);

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

            {data && pipelineProgress ? (
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
                        <h2>Pipeline Progress</h2>
                        <p>These bars measure the complete durable workload. Batch jobs below only describe how package work was dispatched.</p>
                        {([
                            ['GovInfo packages', pipelineProgress.packages, 'Package jobs succeeded'],
                            ['OpenSearch indexing', pipelineProgress.indexing, 'Index jobs succeeded'],
                            ['GovInfo coverage', pipelineProgress.coverage, 'Live package-job state'],
                        ] as const).map(([label, progress, description]) => {
                            const percentage = formatPct(progress.completed, progress.target);
                            return (
                                <div className="progress-row" key={label}>
                                    <div className="progress-label">{label}</div>
                                    <div className="progress-track" role="progressbar" aria-label={`${label} completion`} aria-valuemin={0} aria-valuemax={progress.target} aria-valuenow={progress.completed}>
                                        <div className="progress-fill progress-fill-hydrated" style={{ width: `${Math.min(100, Number(percentage))}%` }} />
                                    </div>
                                    <div className="progress-metric">{progress.completed.toLocaleString()} / {progress.target.toLocaleString()} ({percentage}%) · {progress.queued.toLocaleString()} queued · {progress.running.toLocaleString()} running · {description}</div>
                                </div>
                            );
                        })}
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
                                        <th>Completed</th>
                                        <th>Observed</th>
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
