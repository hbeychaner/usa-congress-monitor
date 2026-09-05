import { Card, Flex, Grid, Heading, Text } from '@radix-ui/themes';
import { Link } from 'react-router-dom';

const DESTINATIONS = [
  { to: '/states', title: 'Map View', description: 'Browse states and view their current congressional delegation.' },
  { to: '/bills', title: 'Bill Activity', description: 'Browse recently updated bills from OpenSearch.' },
  { to: '/topics', title: 'Topic Explorer', description: 'Explore indexed topic associations.' },
  { to: '/search', title: 'Global Search', description: 'Run typed member/state/bill queries with backend relevance scoring.' },
];

export function HomePage() {
  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8">Congress Tracker</Heading>
        <Text color="gray">Search the congressional record, browse states, and inspect members.</Text>
      </Flex>

      <Grid columns={{ initial: '1', sm: '2' }} gap="4">
        {DESTINATIONS.map((destination) => (
          <Card key={destination.to} asChild size="3">
            <Link to={destination.to}>
              <Heading size="4" mb="1">{destination.title}</Heading>
              <Text color="gray">{destination.description}</Text>
            </Link>
          </Card>
        ))}
      </Grid>
    </Flex>
  );
}
