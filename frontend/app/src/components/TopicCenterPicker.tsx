import { Button, Flex, SegmentedControl, Text, TextField } from '@radix-ui/themes';
import { useCallback, useMemo, useState } from 'react';

import type { CenterKind } from '../api/graph';
import type { AnalysisStatus } from '../api/analysis';
import { fetchSubjects } from '../api/subjects';
import { fetchMetasubjects, fetchTopics } from '../api/topics';
import { useRead } from '../hooks/useRead';
import { AnalysisNotice } from './AnalysisNotice';

const MAX_OPTIONS = 14;

type CenterOption = { key: string; label: string };

type Props = {
  kind: CenterKind;
  selectedKey: string | null;
  onChange: (kind: CenterKind, key: string | null) => void;
};

async function loadOptions(kind: CenterKind): Promise<{ options: CenterOption[]; analysis: AnalysisStatus | null }> {
  if (kind === 'metasubject') {
    const response = await fetchMetasubjects();
    return {
      options: response.metasubjects.map((group) => ({ key: String(group.metasubject_id), label: group.name })),
      analysis: response.analysis,
    };
  }
  if (kind === 'topic') {
    const response = await fetchTopics();
    return { options: response.topics
      .filter((topic) => topic.topic_id >= 0)
      .map((topic) => ({ key: String(topic.topic_id), label: topic.label })), analysis: response.analysis };
  }
  const response = await fetchSubjects(undefined, 500);
  return { options: response.subjects.map((subject) => ({ key: subject.name, label: subject.name })), analysis: null };
}

export function TopicCenterPicker({ kind, selectedKey, onChange }: Props) {
  const request = useCallback(() => loadOptions(kind), [kind]);
  const { data, error, loading } = useRead(request);
  const options = useMemo(() => data?.options ?? [], [data]);
  const [filter, setFilter] = useState('');

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return options.filter((option) => !needle || option.label.toLowerCase().includes(needle)).slice(0, MAX_OPTIONS);
  }, [options, filter]);
  const selectedLabel = options.find((option) => option.key === selectedKey)?.label ?? selectedKey;

  return (
    <Flex direction="column" gap="3">
      <AnalysisNotice label="Graph centers" analysis={data?.analysis} error={error} loading={loading} />
      <Flex gap="3" align="end" wrap="wrap">
        <SegmentedControl.Root size="1" value={kind} onValueChange={(value) => onChange(value as CenterKind, null)}>
          <SegmentedControl.Item value="metasubject">Metasubject</SegmentedControl.Item>
          <SegmentedControl.Item value="topic">Topic</SegmentedControl.Item>
          <SegmentedControl.Item value="subject">CRS subject</SegmentedControl.Item>
        </SegmentedControl.Root>
        <TextField.Root value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter" />
        {selectedKey ? <Text size="2" weight="medium">Centered on: {selectedLabel}</Text> : null}
      </Flex>
      {!loading && !error && !visible.length && (!data?.analysis || data.analysis.state === 'available') ? (
        <Text color="gray">No centers match this filter.</Text>
      ) : null}
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
