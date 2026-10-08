import { Badge, Button, Callout, Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';

import { fetchTopicTraining, startTopicTraining, type TopicTrainingStatus } from '../api/admin';

const STATE_COLORS: Record<string, 'gray' | 'blue' | 'green' | 'red'> = {
  idle: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
};

function formatTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : 'n/a';
}

export function TopicTrainingCard() {
  const [status, setStatus] = useState<TopicTrainingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await fetchTopicTraining();
        if (!cancelled) setStatus(next);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    }
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      setStatus(await startTopicTraining());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  const running = status?.state === 'running';

  return (
    <Card size="3">
      <Flex direction="column" gap="3">
        <Flex justify="between" align="center" wrap="wrap" gap="3">
          <Flex align="center" gap="3">
            <Heading size="4">Topic model</Heading>
            <Badge color={STATE_COLORS[status?.state ?? 'idle'] ?? 'gray'}>{status?.state ?? 'unknown'}</Badge>
          </Flex>
          <Button onClick={start} disabled={running || starting}>
            {running ? 'Training in progress' : 'Retrain now'}
          </Button>
        </Flex>
        <Text size="2" color="gray">
          Retrains on every bill and rewrites topics and assignments. Runs automatically every Sunday at 06:00 and takes a while on CPU.
        </Text>
        {status ? (
          <Flex gap="5" wrap="wrap">
            {status.stage ? <Text size="2"><Text weight="bold">Stage:</Text> {status.stage}</Text> : null}
            <Text size="2"><Text weight="bold">Started:</Text> {formatTime(status.started_at)}</Text>
            <Text size="2"><Text weight="bold">Finished:</Text> {formatTime(status.finished_at)}</Text>
            {status.model_version ? <Text size="2"><Text weight="bold">Version:</Text> {status.model_version}</Text> : null}
            {status.message ? <Text size="2">{status.message}</Text> : null}
          </Flex>
        ) : null}
        {error ? (
          <Callout.Root color="red">
            <Callout.Text>{error}</Callout.Text>
          </Callout.Root>
        ) : null}
      </Flex>
    </Card>
  );
}
