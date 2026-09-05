import { Badge, Callout, Card, Flex, Grid, Heading, Progress, Select, Table, Text } from '@radix-ui/themes';
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
        <Flex direction="column" gap="5">
            <Flex direction="column" gap="2">
                <Heading size="7">Ingest Admin</Heading>
                <Text color="gray">Live acquisition and indexing state. Auto-refreshes every 10 seconds.</Text>
            </Flex>

            <Card size="3">
                <Flex gap="5" wrap="wrap">
                    <Text><Text weight="bold">Last updated:</Text> {lastUpdated ? lastUpdated.toLocaleTimeString() : 'n/a'}</Text>
                    <Text><Text weight="bold">Active jobs:</Text> {data?.active_jobs ?? 0}</Text>
                </Flex>
            </Card>

            {error ? (
                <Callout.Root color="red">
                    <Callout.Text>Failed to load progress: {error}</Callout.Text>
                </Callout.Root>
            ) : null}

            {loading && !data ? <Card size="3"><Text as="p">Loading ingest progress...</Text></Card> : null}

            {data && pipelineProgress ? (
                <>
                    {snapshot ? (
                        <Grid columns={{ initial: '1', md: '3' }} gap="4">
                            <Card size="3">
                                <Flex direction="column" gap="1">
                                    <Text size="1" color="gray">118th Congress</Text>
                                    <Heading size="4">{snapshot.ready_for_reconciliation ? 'Ready for reconciliation' : 'Acquisition in progress'}</Heading>
                                    <Badge color={snapshot.ready_for_reconciliation ? 'green' : 'amber'} variant="soft" style={{ width: 'fit-content' }}>
                                        {snapshot.ready_for_reconciliation ? 'Ready' : 'Blocked'}
                                    </Badge>
                                    <Text color="gray">{snapshot.govinfo.pending.toLocaleString()} packages remain before the complete-coverage gate opens.</Text>
                                </Flex>
                            </Card>
                            <Card size="3">
                                <Flex direction="column" gap="1">
                                    <Text size="1" color="gray">GovInfo coverage</Text>
                                    <Heading size="5">{snapshot.govinfo.available.toLocaleString()} / {snapshot.govinfo.expected.toLocaleString()}</Heading>
                                    <Text color="gray">{snapshot.govinfo.failed + snapshot.govinfo.not_available} classified gaps · {snapshot.govinfo.pending.toLocaleString()} pending</Text>
                                </Flex>
                            </Card>
                            <Card size="3">
                                <Flex direction="column" gap="1">
                                    <Text size="1" color="gray">Staging index</Text>
                                    <Heading size="5">{snapshot.staging.documents.toLocaleString()} documents</Heading>
                                    <Text color="gray">{snapshot.staging.exists ? snapshot.staging.index : 'Not created'} · {snapshot.staging.connected ? 'OpenSearch connected' : 'OpenSearch unavailable'}</Text>
                                </Flex>
                            </Card>
                        </Grid>
                    ) : null}

                    {snapshot ? (
                        <Card size="3">
                            <Heading size="4" mb="3">Pipeline Status</Heading>
                            <Grid columns={{ initial: '1', sm: '2', md: '3' }} gap="4">
                                <Flex direction="column"><Text size="1" color="gray">GovInfo packages</Text><Text weight="bold">{snapshot.govinfo_jobs.queued.toLocaleString()} queued · {snapshot.govinfo_jobs.running} running</Text></Flex>
                                <Flex direction="column"><Text size="1" color="gray">GovInfo batches</Text><Text weight="bold">{snapshot.govinfo_batch_jobs.queued.toLocaleString()} queued · {snapshot.govinfo_batch_jobs.running} running</Text></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Index jobs</Text><Text weight="bold">{snapshot.index_jobs.queued.toLocaleString()} queued · {snapshot.index_jobs.failed} failed</Text></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Reconciliation</Text><Text weight="bold">{snapshot.reconcile_jobs.succeeded} complete · {snapshot.reconcile_jobs.running} running</Text></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Production read alias</Text><Text weight="bold">{snapshot.staging.production_alias_target ?? 'Unavailable'}</Text></Flex>
                            </Grid>
                        </Card>
                    ) : null}

                    <Card size="3">
                        <Heading size="4" mb="1">Pipeline Progress</Heading>
                        <Text as="p" color="gray" mb="3">These bars measure the complete durable workload. Batch jobs below only describe how package work was dispatched.</Text>
                        <Flex direction="column" gap="4">
                            {([
                                ['GovInfo packages', pipelineProgress.packages, 'Package jobs succeeded'],
                                ['OpenSearch indexing', pipelineProgress.indexing, 'Index jobs succeeded'],
                                ['GovInfo coverage', pipelineProgress.coverage, 'Live package-job state'],
                            ] as const).map(([label, progress, description]) => {
                                const percentage = formatPct(progress.completed, progress.target);
                                return (
                                    <Flex direction="column" gap="1" key={label}>
                                        <Text weight="medium">{label}</Text>
                                        <Progress value={Math.min(100, Number(percentage))} aria-label={`${label} completion`} />
                                        <Text size="1" color="gray">{progress.completed.toLocaleString()} / {progress.target.toLocaleString()} ({percentage}%) · {progress.queued.toLocaleString()} queued · {progress.running.toLocaleString()} running · {description}</Text>
                                    </Flex>
                                );
                            })}
                        </Flex>
                    </Card>

                    <Card size="3">
                        <Flex justify="between" align="center" wrap="wrap" gap="3" mb="2">
                            <Heading size="4">Per Job</Heading>
                            <label>
                                <Text as="div" size="2" mb="1" weight="medium">Status</Text>
                                <Select.Root value={statusFilter || 'all'} onValueChange={(value) => setStatusFilter(value === 'all' ? '' : value)}>
                                    <Select.Trigger />
                                    <Select.Content>
                                        <Select.Item value="all">All statuses</Select.Item>
                                        <Select.Item value="queued">Queued</Select.Item>
                                        <Select.Item value="running">Running</Select.Item>
                                        <Select.Item value="retrying">Retrying</Select.Item>
                                    </Select.Content>
                                </Select.Root>
                            </label>
                        </Flex>
                        {data.jobs.length > 0 ? <Text as="p" size="2" color="gray" mb="2">Showing {filteredJobs.length.toLocaleString()} of {data.jobs.length.toLocaleString()} active jobs</Text> : null}
                        {data.jobs.length === 0 ? (
                            <Text as="p">No active ingest jobs.</Text>
                        ) : filteredJobs.length === 0 ? (
                            <Text as="p">No active jobs match this status.</Text>
                        ) : (
                            <Table.Root variant="surface">
                                <Table.Header>
                                    <Table.Row>
                                        <Table.ColumnHeaderCell>Job</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Status</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Resource</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Window</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Completed</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Observed</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Target</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Remaining</Table.ColumnHeaderCell>
                                    </Table.Row>
                                </Table.Header>
                                <Table.Body>
                                    {filteredJobs.map((job) => (
                                        <Table.Row key={job.job_id}>
                                            <Table.RowHeaderCell>{job.job_id.replace('ingest:', '').slice(0, 10)}</Table.RowHeaderCell>
                                            <Table.Cell><Badge variant="soft">{job.status}</Badge></Table.Cell>
                                            <Table.Cell>{job.resource}</Table.Cell>
                                            <Table.Cell>{formatDate(job.from_date)} to {formatDate(job.to_date)}</Table.Cell>
                                            <Table.Cell>{job.hydrated.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{job.discovered.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{job.target.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{job.remaining.toLocaleString()}</Table.Cell>
                                        </Table.Row>
                                    ))}
                                </Table.Body>
                            </Table.Root>
                        )}
                    </Card>
                </>
            ) : null}
        </Flex>
    );
}
