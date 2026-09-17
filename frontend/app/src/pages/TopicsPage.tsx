import { Badge, Card, Flex, Grid, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchSubjects } from '../api/subjects';
import type { SubjectsResponse } from '../api/subjects';
import { fetchTopics } from '../api/topics';
import type { TopicsResponse } from '../api/topics';

export function TopicsPage() {
  const [data, setData] = useState<TopicsResponse | null>(null);
  const [subjects, setSubjects] = useState<SubjectsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopics()
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
    fetchSubjects().then(setSubjects).catch(() => setSubjects(null));
  }, []);

  const topics = data?.topics ?? [];

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8">Topics</Heading>
        <Text color="gray">
          Topics discovered from bill titles and summaries by the BERTopic pipeline.
          {data?.trained_at ? ` Last trained ${new Date(data.trained_at).toLocaleString()}.` : ''}
        </Text>
      </Flex>

      {loading && <Text as="p">Loading topics…</Text>}
      {error && <Text as="p" color="red">Failed to load topics: {error}</Text>}
      {!loading && !error && topics.length === 0 && (
        <Card size="3">
          <Text as="p" color="gray">
            No trained topic model yet. Run <code>scripts/train_topic_model.py</code> to populate topics.
          </Text>
        </Card>
      )}

      <Grid columns={{ initial: '1', sm: '2', md: '3' }} gap="4">
        {topics.map((topic) => (
          <Card key={topic.topic_id} size="3">
            <Heading size="4" mb="1" style={{ textTransform: 'capitalize' }}>
              <Link to={`/topics/${topic.topic_id}`}>{topic.label}</Link>
            </Heading>
            <Text as="p" color="gray" mb="2">{topic.size} bills</Text>
            <Flex gap="1" wrap="wrap">
              {topic.top_words.slice(0, 6).map((word) => (
                <Badge key={word} variant="soft">{word}</Badge>
              ))}
            </Flex>
          </Card>
        ))}
      </Grid>

      {subjects && (subjects.policy_areas.length > 0 || subjects.subjects.length > 0) ? (
        <Card size="3">
          <Heading size="4" mb="1">Legislative Subjects (CRS)</Heading>
          <Text as="p" color="gray" mb="3">
            Human-annotated subject terms assigned by the Congressional Research Service across {subjects.total_bills.toLocaleString()} bills.
          </Text>
          {subjects.policy_areas.length > 0 ? (
            <Flex direction="column" gap="2" mb="3">
              <Heading size="3">Policy areas</Heading>
              <Flex gap="1" wrap="wrap">
                {subjects.policy_areas.map((item) => (
                  <Badge key={item.name} asChild>
                    <Link to={`/bills?subject=${encodeURIComponent(item.name)}`}>{item.name} · {item.count.toLocaleString()}</Link>
                  </Badge>
                ))}
              </Flex>
            </Flex>
          ) : null}
          {subjects.subjects.length > 0 ? (
            <Flex direction="column" gap="2">
              <Heading size="3">Subjects</Heading>
              <Flex gap="1" wrap="wrap">
                {subjects.subjects.map((item) => (
                  <Badge key={item.name} variant="soft" asChild>
                    <Link to={`/bills?subject=${encodeURIComponent(item.name)}`}>{item.name} · {item.count.toLocaleString()}</Link>
                  </Badge>
                ))}
              </Flex>
            </Flex>
          ) : null}
        </Card>
      ) : null}
    </Flex>
  );
}
