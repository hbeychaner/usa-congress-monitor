import { Badge, Card, Flex, Heading, Table, Text, TextField } from '@radix-ui/themes';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { fetchTopic } from '../api/topics';
import type { TopicDetailResponse } from '../api/topics';
import { HorizontalBarChart } from '../components/HorizontalBarChart';
import { TrendLineChart } from '../components/TrendLineChart';
import type { TrendSeries } from '../components/TrendLineChart';

function trendToSeries(label: string, trend: TopicDetailResponse['trend']): TrendSeries[] {
  const byYear = new Map<number, number>();
  for (const point of trend) {
    const year = new Date(point.timestamp).getFullYear();
    if (!Number.isFinite(year)) continue;
    byYear.set(year, (byYear.get(year) ?? 0) + point.frequency);
  }
  if (byYear.size < 2) return [];
  const years = [...byYear.keys()];
  const min = Math.min(...years);
  const max = Math.max(...years);
  const grid = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return [{ name: label, points: grid.map((year) => [year, byYear.get(year) ?? 0]) }];
}

export function TopicDetailPage() {
  const { topicId = '' } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<TopicDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [billQuery, setBillQuery] = useState('');

  useEffect(() => {
    fetchTopic(Number(topicId), 100)
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [topicId]);

  const series = useMemo(
    () => (data ? trendToSeries(data.topic.label, data.trend) : []),
    [data],
  );
  // Labels can repeat across topics, so suffix the id to keep bars distinguishable.
  const relatedBars = useMemo(() => {
    const related = data?.related ?? [];
    const counts = new Map<string, number>();
    related.forEach((item) => counts.set(item.label, (counts.get(item.label) ?? 0) + 1));
    return related.map((item) => ({
      label: (counts.get(item.label) ?? 0) > 1 ? `${item.label} (#${item.topic_id})` : item.label,
      value: item.similarity,
      topicId: item.topic_id,
    }));
  }, [data]);
  const filteredBills = useMemo(() => {
    const bills = data?.top_bills ?? [];
    const needle = billQuery.trim().toLowerCase();
    if (!needle) return bills;
    return bills.filter(
      (bill) =>
        (bill.title ?? '').toLowerCase().includes(needle) ||
        bill.bill_id.toLowerCase().includes(needle),
    );
  }, [data, billQuery]);

  if (loading) return <Text as="p">Loading topic…</Text>;
  if (error || !data) return <Text as="p" color="red">Failed to load topic: {error}</Text>;

  const { topic, top_bills: topBills } = data;

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8" style={{ textTransform: 'capitalize' }}>{topic.label}</Heading>
        <Text color="gray">{topic.size.toLocaleString()} bills assigned to this topic.</Text>
        <Flex gap="1" wrap="wrap">
          {topic.top_words.map((word) => (
            <Badge key={word} variant="soft">{word}</Badge>
          ))}
        </Flex>
      </Flex>

      {series.length > 0 && (
        <Card size="3">
          <Heading size="4" mb="2">Activity Over Time</Heading>
          <TrendLineChart series={series} height={260} />
        </Card>
      )}

      {relatedBars.length > 0 && (
        <Card size="3">
          <Heading size="4" mb="2">Related Topics</Heading>
          <HorizontalBarChart
            data={relatedBars.map(({ label, value }) => ({ label, value }))}
            formatValue={(value) => `${Math.round(value * 100)}%`}
            onBarClick={(label) => {
              const match = relatedBars.find((bar) => bar.label === label);
              if (match) navigate(`/topics/${match.topicId}`);
            }}
          />
          <Text size="1" color="gray">Similarity of topic embeddings; click a bar to open the topic.</Text>
        </Card>
      )}

      <Card size="3">
        <Flex justify="between" align="center" wrap="wrap" gap="3" mb="2">
          <Heading size="4">Related Bills ({filteredBills.length})</Heading>
          {topBills.length > 0 && (
            <TextField.Root
              placeholder="Filter bills…"
              value={billQuery}
              onChange={(event) => setBillQuery(event.target.value)}
              style={{ width: 220 }}
            />
          )}
        </Flex>
        {topBills.length === 0 ? (
          <Text as="p" color="gray">No bill assignments indexed for this topic.</Text>
        ) : filteredBills.length === 0 ? (
          <Text as="p" color="gray">No bills match “{billQuery}”.</Text>
        ) : (
          <Table.Root>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Bill</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Confidence</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {filteredBills.map((bill) => (
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
