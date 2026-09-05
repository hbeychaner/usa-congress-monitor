import { Badge, Button, Card, DataList, Flex, Grid, Heading, Text } from '@radix-ui/themes';
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

    if (error) {
        return (
            <Card size="3">
                <Heading size="5" mb="1">Bill unavailable</Heading>
                <Text as="p">{error}</Text>
                <Link to="/bills">Back to bills</Link>
            </Card>
        );
    }
    if (!response) return <Card size="3"><Text as="p">Loading bill...</Text></Card>;

    const bill = response.bill;
    const action = bill.latest_action as RecordValue | null;
    const subjects = bill.subjects?.legislativeSubjects;
    const sponsors = bill.sponsors ?? [];
    const relationshipCounts = bill.relationship_counts ?? {};

    return (
        <Flex direction="column" gap="5">
            <Link to="/bills">Back to bills</Link>
            <Flex justify="between" align="start" wrap="wrap" gap="3">
                <Flex direction="column" gap="1">
                    <Text size="1" color="gray">{bill.bill_type ?? 'Bill'} {bill.number ?? ''} · Congress {bill.congress ?? 'Unknown'}</Text>
                    <Heading size="7">{bill.title}</Heading>
                    <Text color="gray">{bill.origin_chamber ?? 'Chamber not recorded'} · Introduced {formatDate(bill.introduced_date)}</Text>
                </Flex>
                <Button asChild>
                    <a href={`https://www.congress.gov/bill/${bill.congress}/${(bill.bill_type ?? '').toLowerCase()}/${bill.number}`} target="_blank" rel="noreferrer">View on Congress.gov</a>
                </Button>
            </Flex>

            <Grid columns={{ initial: '1', md: '3' }} gap="4">
                <Flex direction="column" gap="4" style={{ gridColumn: 'span 2' }}>
                    <Card size="3">
                        <Heading size="4" mb="2">Latest action</Heading>
                        {action ? (
                            <Flex direction="column" gap="1">
                                <Text weight="bold">{formatDate(String(action.action_date ?? ''))}</Text>
                                <Text color="gray">{String(action.text ?? 'Action text not recorded')}</Text>
                            </Flex>
                        ) : <Text as="p" color="gray">No action is recorded for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Policy and subjects</Heading>
                        {bill.policy_area ? <Badge mb="2">{bill.policy_area}</Badge> : <Text as="p" color="gray">Policy area not recorded.</Text>}
                        {Array.isArray(subjects) && subjects.length > 0 ? (
                            <Flex direction="column" gap="1" mt="2">
                                {subjects.map((subject, index) => (
                                    <Text as="p" key={`${String(subject.name ?? subject.title ?? index)}`}>
                                        {String(subject.name ?? subject.title ?? 'Unnamed subject')}
                                    </Text>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">Legislative subjects are not expanded in this record.</Text>}
                    </Card>
                    {bill.full_text ? (
                        <Card size="3" asChild>
                            <details>
                                <summary><Text weight="medium">Bill text</Text></summary>
                                <Text as="p" mt="2" style={{ whiteSpace: 'pre-wrap' }}>{bill.full_text}</Text>
                            </details>
                        </Card>
                    ) : null}
                </Flex>

                <Flex direction="column" gap="4">
                    <Card size="3">
                        <Heading size="4" mb="2">Bill record</Heading>
                        <DataList.Root>
                            <DataList.Item><DataList.Label>Type</DataList.Label><DataList.Value>{bill.bill_type ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Number</DataList.Label><DataList.Value>{bill.number ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Origin chamber</DataList.Label><DataList.Value>{bill.origin_chamber ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Last updated</DataList.Label><DataList.Value>{formatDate(bill.update_date)}</DataList.Value></DataList.Item>
                        </DataList.Root>
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Sponsors</Heading>
                        {sponsors.length ? (
                            <Flex direction="column" gap="2">
                                {sponsors.map((sponsor) => (
                                    <Flex direction="column" key={String(sponsor.id ?? displayName(sponsor))}>
                                        <Text weight="bold">{displayName(sponsor)}</Text>
                                        {sponsor.party || sponsor.state ? (
                                            <Text size="1" color="gray">{[sponsor.party, sponsor.state, sponsor.district ? `District ${sponsor.district}` : ''].filter(Boolean).join(' · ')}</Text>
                                        ) : null}
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No sponsors are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Available records</Heading>
                        {Object.keys(relationshipCounts).length ? (
                            <DataList.Root>
                                {Object.entries(relationshipCounts).map(([name, count]) => (
                                    <DataList.Item key={name}>
                                        <DataList.Label>{name.replace(/_/g, ' ')}</DataList.Label>
                                        <DataList.Value>{count}</DataList.Value>
                                    </DataList.Item>
                                ))}
                            </DataList.Root>
                        ) : <Text as="p" color="gray">No related record counts are available.</Text>}
                    </Card>
                </Flex>
            </Grid>
        </Flex>
    );
}
