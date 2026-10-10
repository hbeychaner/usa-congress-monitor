import { Badge, Button, Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchCommittee, type CommitteeDetailResponse } from '../api/committees';

const PAGE_SIZE = 50;

function formatDate(value: string | null): string {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

export function CommitteeDetailPage() {
    const { systemCode = '' } = useParams();
    const [page, setPage] = useState(1);
    const [response, setResponse] = useState<CommitteeDetailResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => setPage(1), [systemCode]);

    useEffect(() => {
        setResponse(null);
        setError(null);
        fetchCommittee(systemCode, page, PAGE_SIZE).then(setResponse).catch((err: Error) => setError(err.message));
    }, [systemCode, page]);

    if (error) {
        return (
            <Card size="3">
                <Heading size="5" mb="1">Committee unavailable</Heading>
                <Text as="p">{error}</Text>
                <Link to="/bills">Back to bills</Link>
            </Card>
        );
    }
    if (!response) return <Card size="3"><Text as="p">Loading committee...</Text></Card>;

    const lastPage = Math.max(1, Math.ceil(response.total / PAGE_SIZE));
    return (
        <Flex direction="column" gap="4">
            <Link to="/bills">Back to bills</Link>
            <Flex direction="column" gap="1">
                <Heading size="7">{response.name}</Heading>
                <Flex gap="2" align="center">
                    {response.chamber ? <Badge>{response.chamber}</Badge> : null}
                    {response.committee_type ? <Badge variant="soft">{response.committee_type}</Badge> : null}
                    <Text color="gray">{response.total.toLocaleString()} referred bills</Text>
                </Flex>
            </Flex>
            <Card size="3">
                <Flex direction="column" gap="3">
                    {response.bills.map((bill) => (
                        <Flex direction="column" gap="1" key={bill.bill_id}>
                            <Link to={`/bills/${encodeURIComponent(bill.bill_id)}`}>
                                <Text weight="bold">{bill.title}</Text>
                            </Link>
                            <Text size="1" color="gray">
                                {[
                                    bill.congress ? `Congress ${bill.congress}` : '',
                                    ...bill.activities.map((activity) => `${activity.name} ${formatDate(activity.date)}`.trim()),
                                ].filter(Boolean).join(' · ')}
                            </Text>
                        </Flex>
                    ))}
                </Flex>
            </Card>
            <Flex gap="3" align="center">
                <Button variant="soft" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <Text size="2" color="gray">Page {page} of {lastPage}</Text>
                <Button variant="soft" disabled={page >= lastPage} onClick={() => setPage(page + 1)}>Next</Button>
            </Flex>
        </Flex>
    );
}
