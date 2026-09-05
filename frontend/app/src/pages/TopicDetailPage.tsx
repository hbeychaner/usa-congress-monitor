import { Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useParams } from 'react-router-dom';

export function TopicDetailPage() {
  const { topicLabel = 'topic' } = useParams();
  const title = topicLabel.replace(/-/g, ' ');

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8" style={{ textTransform: 'capitalize' }}>{title}</Heading>
        <Text color="gray">Topic detail scaffold page for explaining member-topic associations and provenance.</Text>
      </Flex>

      <Card size="3">
        <Heading size="4" mb="1">Topic Notes</Heading>
        <Text as="p">
          Placeholder: backend NLP pipeline will return representative phrases and bill references for this topic.
        </Text>
      </Card>

      <Card size="3">
        <Heading size="4" mb="1">Related Members</Heading>
        <Text as="p" color="gray">No indexed member associations are available for this topic.</Text>
      </Card>
    </Flex>
  );
}
