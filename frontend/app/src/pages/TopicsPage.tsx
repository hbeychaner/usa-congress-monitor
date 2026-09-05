import { Card, Flex, Grid, Heading, Progress, Text } from '@radix-ui/themes';
import { Link } from 'react-router-dom';

const SAMPLE_TOPICS = [
  {
    label: 'Energy Transition',
    memberCount: 72,
    avgConfidence: 0.78,
  },
  {
    label: 'Infrastructure',
    memberCount: 65,
    avgConfidence: 0.71,
  },
  {
    label: 'Healthcare Access',
    memberCount: 59,
    avgConfidence: 0.67,
  },
];

export function TopicsPage() {
  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8">Topics</Heading>
        <Text color="gray">
          Topic profiles are scaffolded for now and will be populated from backend NLP pipelines as ingest completes.
        </Text>
      </Flex>

      <Grid columns={{ initial: '1', sm: '2', md: '3' }} gap="4">
        {SAMPLE_TOPICS.map((topic) => (
          <Card key={topic.label} size="3">
            <Heading size="4" mb="1">
              <Link to={`/topics/${topic.label.toLowerCase().replace(/\s+/g, '-')}`}>{topic.label}</Link>
            </Heading>
            <Text as="p" color="gray">Members tagged: {topic.memberCount}</Text>
            <Text as="p" color="gray" mb="2">Average confidence: {Math.round(topic.avgConfidence * 100)}%</Text>
            <Progress value={Math.round(topic.avgConfidence * 100)} />
          </Card>
        ))}
      </Grid>

      <Card size="3">
        <Heading size="4" mb="1">Planned Backend Contract</Heading>
        <Text as="p">
          The final UI will consume <strong>GET /api/v1/members/{'{id}'}/topics</strong> plus aggregate topic endpoints.
        </Text>
        <Text as="p">
          For now, explore an archived <Link to="/members/H001092">member profile</Link>.
        </Text>
      </Card>
    </Flex>
  );
}
