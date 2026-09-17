import { Badge, Card, Flex, Heading, Table, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchTopic } from '../api/topics';
import type { TopicDetailResponse } from '../api/topics';

function TrendBars({ trend }: { trend: TopicDetailResponse['trend'] }) {
  const max = Math.max(...trend.map((point) => point.frequency), 1);
  return (
    <Flex align="end" gap="1" style={{ height: 120 }}>
      {trend.map((point) => (
        <div
          key={point.timestamp}
          title={`${new Date(point.timestamp).toLocaleDateString()}: ${point.frequency} bills`}
          style={{
            flex: 1,
            minWidth: 3,
            height: `${Math.max((point.frequency / max) * 100, 2)}%`,
            background: 'var(--accent-9)',
            borderRadius: 2,
          }}
        />
      ))}
    </Flex>
  );
}

export function TopicDetailPage() {
  const { topicId = '' } = useParams();
  const [data, setData] = useState<TopicDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopic(Number(topicId))
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [topicId]);

  if (loading) return <Text as="p">Loading topic…</Text>;
  if (error || !data) return <Text as="p" color="red">Failed to load topic: {error}</Text>;

  const { topic, trend, top_bills: topBills } = data;

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8" style={{ textTransform: 'capitalize' }}>{topic.label}</Heading>
        <Text color="gray">{topic.size} bills assigned to this topic.</Text>
        <Flex gap="1" wrap="wrap">
          {topic.top_words.map((word) => (
            <Badge key={word} variant="soft">{word}</Badge>
          ))}
        </Flex>
      </Flex>

      {trend.length > 0 && (
        <Card size="3">
          <Heading size="4" mb="2">Activity Over Time</Heading>
          <TrendBars trend={trend} />
          <Flex justify="between" mt="1">
            <Text size="1" color="gray">{new Date(trend[0].timestamp).toLocaleDateString()}</Text>
            <Text size="1" color="gray">{new Date(trend[trend.length - 1].timestamp).toLocaleDateString()}</Text>
          </Flex>
        </Card>
      )}

      <Card size="3">
        <Heading size="4" mb="2">Representative Bills</Heading>
        {topBills.length === 0 ? (
          <Text as="p" color="gray">No bill assignments indexed for this topic.</Text>
        ) : (
          <Table.Root>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Bill</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Confidence</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {topBills.map((bill) => (
                <Table.Row key={bill.bill_id}>
                  <Table.RowHeaderCell>
                    <Link to={`/bills/${encodeURIComponent(bill.bill_id)}`}>
                      {bill.title || bill.bill_id}
                    </Link>
                  </Table.RowHeaderCell>
                  <Table.Cell>{Math.round(bill.probability * 100)}%</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        )}
      </Card>
    </Flex>
  );
}
