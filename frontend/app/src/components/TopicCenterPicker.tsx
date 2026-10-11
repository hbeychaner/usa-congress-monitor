import { Button, Flex, SegmentedControl, Text, TextField } from '@radix-ui/themes';
import { useEffect, useMemo, useState } from 'react';

import type { CenterKind } from '../api/graph';
import { fetchSubjects } from '../api/subjects';
import { fetchMetasubjectTrends, fetchTopics } from '../api/topics';

const MAX_OPTIONS = 14;

type CenterOption = { key: string; label: string };

type Props = {
  kind: CenterKind;
  selectedKey: string | null;
  onChange: (kind: CenterKind, key: string | null) => void;
};

async function loadOptions(kind: CenterKind): Promise<CenterOption[]> {
  if (kind === 'metasubject') {
    const response = await fetchMetasubjectTrends();
    return response.series.map((group) => ({ key: String(group.metasubject_id), label: group.label }));
  }
  if (kind === 'topic') {
    const response = await fetchTopics();
    return response.topics
      .filter((topic) => topic.topic_id >= 0)
      .map((topic) => ({ key: String(topic.topic_id), label: topic.label }));
  }
  const response = await fetchSubjects(undefined, 500);
  return response.subjects.map((subject) => ({ key: subject.name, label: subject.name }));
}

export function TopicCenterPicker({ kind, selectedKey, onChange }: Props) {
  const [options, setOptions] = useState<CenterOption[]>([]);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    let cancelled = false;
    setOptions([]);
    loadOptions(kind).then((loaded) => !cancelled && setOptions(loaded)).catch(() => undefined);
    return () => { cancelled = true; };
  }, [kind]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return options.filter((option) => !needle || option.label.toLowerCase().includes(needle)).slice(0, MAX_OPTIONS);
  }, [options, filter]);
  const selectedLabel = options.find((option) => option.key === selectedKey)?.label ?? selectedKey;

  return (
    <Flex direction="column" gap="3">
      <Flex gap="3" align="end" wrap="wrap">
        <SegmentedControl.Root size="1" value={kind} onValueChange={(value) => onChange(value as CenterKind, null)}>
          <SegmentedControl.Item value="metasubject">Metasubject</SegmentedControl.Item>
          <SegmentedControl.Item value="topic">Topic</SegmentedControl.Item>
          <SegmentedControl.Item value="subject">CRS subject</SegmentedControl.Item>
        </SegmentedControl.Root>
        <TextField.Root value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter" />
        {selectedKey ? <Text size="2" weight="medium">Centered on: {selectedLabel}</Text> : null}
      </Flex>
      <Flex gap="2" wrap="wrap">
        {visible.map((option) => (
          <Button
            key={option.key}
            size="1"
            variant={option.key === selectedKey ? 'solid' : 'outline'}
            onClick={() => onChange(kind, option.key)}
          >
            {option.label}
          </Button>
        ))}
      </Flex>
    </Flex>
  );
}
