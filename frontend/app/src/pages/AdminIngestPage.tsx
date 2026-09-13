import { Badge, Callout, Card, Flex, Grid, Heading, Select, Table, Text } from '@radix-ui/themes';
import { useEffect, useMemo, useState } from 'react';

import { fetchIngestProgress, type IngestProgressResponse } from '../api/admin';

function formatDate(date: string | null): string {
    if (!date) {
        return 'n/a';
    }
    return date;
}

export function AdminIngestPage() {
    const [data, setData] = useState<IngestProgressResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [statusFilter, setStatusFilter] = useState('');

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
