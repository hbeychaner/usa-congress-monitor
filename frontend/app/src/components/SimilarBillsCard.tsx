import { Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { fetchSimilarBills, type SimilarBillsResponse } from '../api/bills';

type Props = { billId: string };

export function SimilarBillsCard({ billId }: Props) {
    const [response, setResponse] = useState<SimilarBillsResponse | null>(null);

    useEffect(() => {
        setResponse(null);
        fetchSimilarBills(billId).then(setResponse).catch(() => setResponse(null));
    }, [billId]);

    if (!response || response.similar.length === 0) return null;

    return (
        <Card size="3">
            <Heading size="4" mb="2">Similar bills</Heading>
            <Flex direction="column" gap="3">
                {response.similar.map((bill) => (
                    <Flex direction="column" key={bill.bill_id}>
                        <Link to={`/bills/${encodeURIComponent(bill.bill_id)}`}>{bill.title}</Link>
                        <Text size="1" color="gray">
                            {bill.congress ? `Congress ${bill.congress} · ` : ''}{Math.round(bill.score * 100)}% similar
                        </Text>
                    </Flex>
                ))}
            </Flex>
        </Card>
    );
}
