import { Badge, Button, Callout, Card, Flex, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';

import { fetchMemberGraph, startMemberGraph, type MemberGraphStatus } from '../api/admin';

const STATE_COLORS: Record<string, 'gray' | 'blue' | 'green' | 'red'> = {
  idle: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
};

function formatTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : 'n/a';
}

export function MemberGraphCard() {
  const [status, setStatus] = useState<MemberGraphStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const next = await fetchMemberGraph();
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
      setStatus(await startMemberGraph());
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
            <Heading size="4">Member graph</Heading>
            <Badge color={STATE_COLORS[status?.state ?? 'idle'] ?? 'gray'}>{status?.state ?? 'unknown'}</Badge>
          </Flex>
          <Button onClick={start} disabled={running || starting}>
            {running ? 'Build in progress' : 'Rebuild now'}
          </Button>
        </Flex>
        <Text size="2" color="gray">
          Rebuilds collaboration and voting edges between members. Runs automatically every Monday at 05:00.
        </Text>
        {status ? (
          <Flex gap="5" wrap="wrap">
            {status.stage ? <Text size="2"><Text weight="bold">Stage:</Text> {status.stage}</Text> : null}
            <Text size="2"><Text weight="bold">Started:</Text> {formatTime(status.started_at)}</Text>
            <Text size="2"><Text weight="bold">Finished:</Text> {formatTime(status.finished_at)}</Text>
            {status.versions && Object.keys(status.versions).length ? <Text size="2"><Text weight="bold">Versions:</Text> {Object.entries(status.versions).map(([signal, version]) => `${signal} ${version}`).join(', ')}</Text> : null}
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
