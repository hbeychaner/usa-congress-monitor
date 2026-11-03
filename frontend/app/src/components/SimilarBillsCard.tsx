import { Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';

import { fetchSimilarBills } from '../api/bills';
import { AnalysisNotice } from './AnalysisNotice';
import { useRead } from '../hooks/useRead';

type Props = { billId: string };

export function SimilarBillsCard({ billId }: Props) {
    const request = useCallback(() => fetchSimilarBills(billId), [billId]);
    const { data: response, error, loading } = useRead(request);

    return (
        <Card size="3">
            <Heading size="4" mb="2">Similar bills</Heading>
            <AnalysisNotice analysis={response?.analysis} error={error} loading={loading} />
            <Flex direction="column" gap="3">
                {response?.similar.map((bill) => (
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
