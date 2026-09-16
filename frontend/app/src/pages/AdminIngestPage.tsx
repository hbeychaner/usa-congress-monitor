import { Badge, Callout, Card, Flex, Grid, Heading, Progress, Select, Table, Text } from '@radix-ui/themes';
import { useEffect, useMemo, useState } from 'react';

import { fetchIngestProgress, fetchSystemStatus, type IngestProgressResponse, type SystemStatusResponse } from '../api/admin';

function formatDate(date: string | null): string {
    if (!date) {
        return 'n/a';
    }
    return date;
}

function formatEta(eta: string | null): string {
    if (!eta) {
        return 'unknown';
    }
    const target = new Date(eta);
    const hoursLeft = (target.getTime() - Date.now()) / 3_600_000;
    const clock = target.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    if (hoursLeft <= 0) {
        return clock;
    }
    const remaining = hoursLeft >= 48
        ? `${Math.round(hoursLeft / 24)} days`
        : hoursLeft >= 1
            ? `${Math.round(hoursLeft)} h`
            : `${Math.max(1, Math.round(hoursLeft * 60))} min`;
    return `${clock} (~${remaining} left)`;
}

export function AdminIngestPage() {
    const [data, setData] = useState<IngestProgressResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [statusFilter, setStatusFilter] = useState('');
    const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function loadStatus() {
            try {
                const status = await fetchSystemStatus();
                if (!cancelled) {
                    setSystemStatus(status);
                }
            } catch {
                if (!cancelled) {
                    setSystemStatus(null);
                }
            }
        }

        loadStatus();
        const timer = window.setInterval(loadStatus, 60000);

        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, []);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                const progress = await fetchIngestProgress();
                if (cancelled) {
                    return;
                }

                const now = Date.now();
                setData(progress);
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
                <Text color="gray">Live Congress API acquisition state. Auto-refreshes every 10 seconds.</Text>
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

            {data ? (
                <>
                    <Card size="3">
                        <Flex direction="column" gap="4">
                            <Flex direction="column" gap="1">
                                <Text size="1" color="gray">Overall ingest activity</Text>
                                <Flex align="center" gap="3" wrap="wrap">
                                    <Heading size="4">
                                        {data.activity === 'continuing'
                                            ? 'Ingest continuing'
                                            : data.activity === 'stalled'
                                                ? 'Ingest stalled'
                                                : data.activity === 'queued'
                                                    ? 'Ingest queued'
                                                    : data.activity === 'waiting'
                                                        ? 'Ingest waiting'
                                                        : 'No ingest active'}
                                    </Heading>
                                    <Badge color={data.activity === 'continuing' ? 'green' : data.activity === 'idle' ? 'gray' : 'amber'} variant="soft">
                                        {data.last_progress_at ? `Last progress ${new Date(data.last_progress_at).toLocaleTimeString()}` : 'No progress heartbeat yet'}
                                    </Badge>
                                </Flex>
                            </Flex>
                            <Grid columns={{ initial: '2', sm: '4' }} gap="4">
                                <Flex direction="column"><Text size="1" color="gray">Hydrated</Text><Heading size="5">{data.hydrated.toLocaleString()}</Heading></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Discovered</Text><Heading size="5">{data.discovered.toLocaleString()}</Heading></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Target</Text><Heading size="5">{data.target.toLocaleString()}</Heading></Flex>
                                <Flex direction="column"><Text size="1" color="gray">Remaining</Text><Heading size="5">{data.remaining.toLocaleString()}</Heading></Flex>
                            </Grid>
                            {data.target > 0 ? (
                                <Flex direction="column" gap="1">
                                    <Progress value={Math.min(100, (data.hydrated / data.target) * 100)} size="3" />
                                    <Text size="1" color="gray">{((data.hydrated / data.target) * 100).toFixed(1)}% of the daily API ingest window hydrated</Text>
                                </Flex>
                            ) : null}
                        </Flex>
                    </Card>

                    {data.backfill ? (
                        <Card size="3">
                            <Flex direction="column" gap="4">
                                <Flex align="center" gap="3" wrap="wrap">
                                    <Heading size="4">GovInfo bulk backfill</Heading>
                                    <Badge color={data.backfill.pending === 0 ? 'green' : data.backfill.rate_per_hour > 0 ? 'blue' : 'amber'} variant="soft">
                                        {data.backfill.pending === 0
                                            ? 'Complete'
                                            : data.backfill.rate_per_hour > 0
                                                ? `${data.backfill.rate_per_hour.toLocaleString()} packages/hour`
                                                : data.backfill.batches_pending > 0
                                                    ? 'Dispatching batches'
                                                    : 'No packages completed in the last hour'}
                                    </Badge>
                                </Flex>
                                <Grid columns={{ initial: '2', sm: '5' }} gap="4">
                                    <Flex direction="column"><Text size="1" color="gray">Packages</Text><Heading size="5">{data.backfill.total.toLocaleString()}</Heading></Flex>
                                    <Flex direction="column"><Text size="1" color="gray">Completed</Text><Heading size="5">{data.backfill.succeeded.toLocaleString()}</Heading></Flex>
                                    <Flex direction="column"><Text size="1" color="gray">Pending</Text><Heading size="5">{data.backfill.pending.toLocaleString()}</Heading></Flex>
                                    <Flex direction="column"><Text size="1" color="gray">Failed</Text><Heading size="5">{data.backfill.failed.toLocaleString()}</Heading></Flex>
                                    <Flex direction="column"><Text size="1" color="gray">Batches waiting</Text><Heading size="5">{data.backfill.batches_pending.toLocaleString()}</Heading></Flex>
                                </Grid>
                                <Flex direction="column" gap="1">
                                    <Progress value={data.backfill.percent} size="3" />
                                    <Flex justify="between" wrap="wrap" gap="2">
                                        <Text size="1" color="gray">{data.backfill.percent.toFixed(1)}% complete</Text>
                                        <Text size="1" color="gray">
                                            {data.backfill.pending === 0
                                                ? 'Backfill finished'
                                                : `Estimated completion: ${formatEta(data.backfill.eta)}`}
                                        </Text>
                                    </Flex>
                                </Flex>
                            </Flex>
                        </Card>
                    ) : null}

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
                                        <Table.ColumnHeaderCell>Progress</Table.ColumnHeaderCell>
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
                                            <Table.Cell style={{ minWidth: 120 }}>
                                                <Flex direction="column" gap="1">
                                                    <Progress value={job.target > 0 ? Math.min(100, (job.hydrated / job.target) * 100) : 0} size="2" />
                                                    <Text size="1" color="gray">{job.target > 0 ? `${((job.hydrated / job.target) * 100).toFixed(0)}%` : 'n/a'}</Text>
                                                </Flex>
                                            </Table.Cell>
                                        </Table.Row>
                                    ))}
                                </Table.Body>
                            </Table.Root>
                        )}
                    </Card>
                </>
            ) : null}

            {systemStatus ? (
                <>
                    <Card size="3">
                        <Flex justify="between" align="center" wrap="wrap" gap="2" mb="2">
                            <Heading size="4">Search Indices</Heading>
                            <Badge color={systemStatus.search_connected ? 'green' : 'red'} variant="soft">
                                {systemStatus.search_connected ? 'Search connected' : 'Search unavailable'}
                            </Badge>
                        </Flex>
                        {systemStatus.indices.length > 0 ? (
                            <Grid columns={{ initial: '2', sm: '4' }} gap="4">
                                {systemStatus.indices.map((index) => (
                                    <Flex direction="column" key={index.name}>
                                        <Text size="1" color="gray">{index.name.replace('congress-', '')}</Text>
                                        <Heading size="5">{index.documents.toLocaleString()}</Heading>
                                    </Flex>
                                ))}
                            </Grid>
                        ) : <Text as="p" color="gray">No indices reported.</Text>}
                    </Card>

                    <Card size="3">
                        <Heading size="4" mb="2">Job Ledger</Heading>
                        {Object.keys(systemStatus.jobs).length > 0 ? (
                            <Table.Root variant="surface">
                                <Table.Header>
                                    <Table.Row>
                                        <Table.ColumnHeaderCell>Kind</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Queued</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Running</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Retrying</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Succeeded</Table.ColumnHeaderCell>
                                        <Table.ColumnHeaderCell>Failed</Table.ColumnHeaderCell>
                                    </Table.Row>
                                </Table.Header>
                                <Table.Body>
                                    {Object.entries(systemStatus.jobs).map(([kind, counts]) => (
                                        <Table.Row key={kind}>
                                            <Table.RowHeaderCell>{kind}</Table.RowHeaderCell>
                                            <Table.Cell>{counts.queued.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{counts.running.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{counts.retrying.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{counts.succeeded.toLocaleString()}</Table.Cell>
                                            <Table.Cell>{counts.failed.toLocaleString()}</Table.Cell>
                                        </Table.Row>
                                    ))}
                                </Table.Body>
                            </Table.Root>
                        ) : <Text as="p" color="gray">No jobs recorded in the ledger.</Text>}
                    </Card>
                </>
            ) : null}
        </Flex>
    );
}
