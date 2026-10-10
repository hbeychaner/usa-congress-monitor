import {
  Badge,
  Box,
  Card,
  Flex,
  Grid,
  Heading,
  Select,
  SegmentedControl,
  Text,
  TextField,
} from '@radix-ui/themes';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchPolicyAreaTrends, fetchSubjects } from '../api/subjects';
import type { PolicyAreaTrendsResponse, SubjectsResponse } from '../api/subjects';
import { fetchMetasubjectTrends, fetchTopicTrends, fetchTopics } from '../api/topics';
import type {
  MetasubjectTrendSeries,
  MetasubjectTrendsResponse,
  TopicSummary,
  TopicTrendSeries,
  TopicTrendsResponse,
  TopicsResponse,
} from '../api/topics';
import { TrendLineChart } from '../components/TrendLineChart';
import type { TrendSeries } from '../components/TrendLineChart';

const TOPIC_PAGE_SIZE = 24;
const METASUBJECT_CHART_TOP = 8;
const OTHER_LABEL = 'Other';

type GroupView = 'count' | 'share';

function groupSeriesToTrend(
  series: MetasubjectTrendSeries[],
  view: GroupView,
): TrendSeries[] {
  const byGroup = series.map((s) => {
    const byYear = new Map<number, number>();
    for (const point of s.points) {
      const year = new Date(point.timestamp).getUTCFullYear();
      if (!Number.isFinite(year)) continue;
      byYear.set(year, (byYear.get(year) ?? 0) + point.frequency);
    }
    const total = [...byYear.values()].reduce((sum, value) => sum + value, 0);
    return { name: s.label, byYear, total };
  });
  const years = new Set(byGroup.flatMap((group) => [...group.byYear.keys()]));
  if (years.size < 2) return [];
  const grid = Array.from(
    { length: Math.max(...years) - Math.min(...years) + 1 },
    (_, i) => Math.min(...years) + i,
  );
  const ranked = [...byGroup].sort((a, b) => b.total - a.total);
  const head = ranked.slice(0, METASUBJECT_CHART_TOP);
  const tail = ranked.slice(METASUBJECT_CHART_TOP);
  const rows = [...head.map((group) => ({ name: group.name, byYear: group.byYear }))];
  if (tail.length > 0) {
    const other = new Map<number, number>();
    for (const group of tail) {
      for (const [year, value] of group.byYear) other.set(year, (other.get(year) ?? 0) + value);
    }
    rows.push({ name: OTHER_LABEL, byYear: other });
  }
  const yearTotals = new Map(
    grid.map((year) => [year, rows.reduce((sum, row) => sum + (row.byYear.get(year) ?? 0), 0)]),
  );
  return rows.map((row) => ({
    name: row.name,
    points: grid.map((year) => {
      const value = row.byYear.get(year) ?? 0;
      const total = yearTotals.get(year) ?? 0;
      const shown = view === 'share' ? (total > 0 ? (value / total) * 100 : 0) : value;
      return [year, Math.round(shown * 10) / 10] as [number, number];
    }),
  }));
}

function topicSeriesToTrend(series: TopicTrendSeries[]): TrendSeries[] {
  const allYears = new Set<number>();
  const binned = series.map((s) => {
    const byYear = new Map<number, number>();
    for (const point of s.points) {
      const year = new Date(point.timestamp).getFullYear();
      if (!Number.isFinite(year)) continue;
      byYear.set(year, (byYear.get(year) ?? 0) + point.frequency);
      allYears.add(year);
    }
    return { name: s.label, byYear };
  });
  if (allYears.size < 2) return [];
  const min = Math.min(...allYears);
  const max = Math.max(...allYears);
  const grid = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return binned.map(({ name, byYear }) => ({
    name,
    points: grid.map((year) => [year, byYear.get(year) ?? 0] as [number, number]),
  }));
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card size="3">
      <Flex direction="column" gap="1">
        <Text size="1" color="gray" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {label}
        </Text>
        <Heading size="6">{value}</Heading>
        {hint ? <Text size="1" color="gray">{hint}</Text> : null}
      </Flex>
    </Card>
  );
}

function TopTopicsChart({ topics }: { topics: TopicSummary[] }) {
  const top = topics.slice(0, 15);
  const max = Math.max(...top.map((topic) => topic.size), 1);
  return (
    <Flex direction="column" gap="2">
      {top.map((topic) => (
        <Flex key={topic.topic_id} align="center" gap="3">
          <Box style={{ width: 220, flexShrink: 0, overflow: 'hidden' }}>
            <Text size="2" style={{ textTransform: 'capitalize' }} truncate>
              <Link to={`/topics/${topic.topic_id}`}>{topic.label}</Link>
            </Text>
          </Box>
          <Box style={{ flex: 1 }}>
            <div
              title={`${topic.label}: ${topic.size.toLocaleString()} bills`}
              style={{
                width: `${Math.max((topic.size / max) * 100, 1)}%`,
                height: 18,
                background: 'var(--accent-9)',
                borderRadius: 3,
              }}
            />
          </Box>
          <Box style={{ width: 64, flexShrink: 0, textAlign: 'right' }}>
            <Text size="2" color="gray">{topic.size.toLocaleString()}</Text>
          </Box>
        </Flex>
      ))}
    </Flex>
  );
}

function PolicyAreaChart({ areas }: { areas: SubjectsResponse['policy_areas'] }) {
  const max = Math.max(...areas.map((area) => area.count), 1);
  return (
    <Flex direction="column" gap="2">
      {areas.map((area) => (
        <Flex key={area.name} align="center" gap="3">
          <Box style={{ width: 220, flexShrink: 0, overflow: 'hidden' }}>
            <Text size="2" truncate>
              <Link to={`/bills?subject=${encodeURIComponent(area.name)}`}>{area.name}</Link>
            </Text>
          </Box>
          <Box style={{ flex: 1 }}>
            <div
              title={`${area.name}: ${area.count.toLocaleString()} bills`}
              style={{
                width: `${Math.max((area.count / max) * 100, 1)}%`,
                height: 18,
                background: 'var(--grass-9)',
                borderRadius: 3,
              }}
            />
          </Box>
          <Box style={{ width: 64, flexShrink: 0, textAlign: 'right' }}>
            <Text size="2" color="gray">{area.count.toLocaleString()}</Text>
          </Box>
        </Flex>
      ))}
    </Flex>
  );
}

export function TopicsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<TopicsResponse | null>(null);
  const [subjects, setSubjects] = useState<SubjectsResponse | null>(null);
  const [trends, setTrends] = useState<TopicTrendsResponse | null>(null);
  const [policyTrends, setPolicyTrends] = useState<PolicyAreaTrendsResponse | null>(null);
  const [groupTrends, setGroupTrends] = useState<MetasubjectTrendsResponse | null>(null);
  const [groupView, setGroupView] = useState<GroupView>('count');
  const [groupFilter, setGroupFilter] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'size' | 'label'>('size');
  const [limit, setLimit] = useState(TOPIC_PAGE_SIZE);

  useEffect(() => {
    fetchTopics()
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
    fetchSubjects().then(setSubjects).catch(() => setSubjects(null));
    fetchTopicTrends(10).then(setTrends).catch(() => setTrends(null));
    fetchPolicyAreaTrends(10).then(setPolicyTrends).catch(() => setPolicyTrends(null));
    fetchMetasubjectTrends().then(setGroupTrends).catch(() => setGroupTrends(null));
  }, []);

  const topics = useMemo(() => data?.topics ?? [], [data]);
  const totalAssigned = useMemo(
    () => topics.reduce((sum, topic) => sum + topic.size, 0),
    [topics],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const inGroup = groupFilter === null
      ? topics
      : topics.filter((topic) => topic.metasubject_id === groupFilter);
    const matches = needle
      ? inGroup.filter(
        (topic) =>
          topic.label.toLowerCase().includes(needle) ||
          topic.top_words.some((word) => word.toLowerCase().includes(needle)),
      )
      : inGroup;
    return [...matches].sort((a, b) =>
      sort === 'size' ? b.size - a.size : a.label.localeCompare(b.label),
    );
  }, [topics, query, sort, groupFilter]);

  const visible = filtered.slice(0, limit);

  const policySeries = useMemo<TrendSeries[]>(
    () =>
      (policyTrends?.series ?? []).map((s) => ({
        name: s.name,
        points: s.points.map((p) => [p.year, p.count] as [number, number]),
      })),
    [policyTrends],
  );
  const topicSeries = useMemo(() => topicSeriesToTrend(trends?.series ?? []), [trends]);
  const groupSeries = useMemo(
    () => groupSeriesToTrend(groupTrends?.series ?? [], groupView),
    [groupTrends, groupView],
  );
  const activeGroup = groupTrends?.series.find((s) => s.metasubject_id === groupFilter);

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="8">Topics</Heading>
        <Text color="gray">
          Topics discovered from bill titles and summaries by the BERTopic pipeline,
          alongside the Congressional Research Service&apos;s human-curated subject terms.
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

      {topics.length > 0 && (
        <>
          <Grid columns={{ initial: '2', md: '4' }} gap="4">
            <StatCard label="Topics" value={topics.length.toLocaleString()} />
            <StatCard label="Bills categorized" value={totalAssigned.toLocaleString()} />
            <StatCard
              label="Model version"
              value={data?.model_version ?? '—'}
              hint={data?.trained_at ? `Trained ${new Date(data.trained_at).toLocaleDateString()}` : undefined}
            />
            <StatCard
              label="CRS-tagged bills"
              value={subjects ? subjects.total_bills.toLocaleString() : '—'}
              hint="Bills with CRS subject annotations"
            />
          </Grid>

          <Card size="3">
            <Heading size="4" mb="1">Policy Area Activity Over Time</Heading>
            <Text as="p" size="2" color="gray" mb="3">
              Bills introduced per year in the largest CRS policy areas. Click a line to browse its bills; drag or scroll to zoom.
            </Text>
            {policySeries.length > 0 ? (
              <TrendLineChart
                series={policySeries}
                onSeriesClick={(name) => navigate(`/bills?subject=${encodeURIComponent(name)}`)}
              />
            ) : (
              <Text as="p" color="gray">No CRS policy-area data indexed yet.</Text>
            )}
          </Card>

          <Card size="3">
            <Flex justify="between" align="center" wrap="wrap" gap="3" mb="1">
              <Heading size="4">Subject Groups Over Time</Heading>
              <SegmentedControl.Root
                value={groupView}
                onValueChange={(value) => setGroupView(value as GroupView)}
              >
                <SegmentedControl.Item value="count">Bills</SegmentedControl.Item>
                <SegmentedControl.Item value="share">Share</SegmentedControl.Item>
              </SegmentedControl.Root>
            </Flex>
            <Text as="p" size="2" color="gray" mb="3">
              Topics grouped into broad subject areas, by year introduced. Click a band to list its topics below.
            </Text>
            {groupSeries.length > 0 ? (
              <TrendLineChart
                series={groupSeries}
                height={340}
                stacked
                onSeriesClick={(name) => {
                  const match = groupTrends?.series.find((s) => s.label === name);
                  if (match) setGroupFilter(match.metasubject_id);
                }}
              />
            ) : (
              <Text as="p" color="gray">No subject groups yet; they appear after the next model training run.</Text>
            )}
          </Card>

          <Card size="3">
            <Heading size="4" mb="1">Discovered Topic Activity</Heading>
            <Text as="p" size="2" color="gray" mb="3">
              Bills per year for the largest machine-discovered topics. Click a line to open the topic.
            </Text>
            {topicSeries.length > 0 ? (
              <TrendLineChart
                series={topicSeries}
                height={280}
                onSeriesClick={(name) => {
                  const match = trends?.series.find((s) => s.label === name);
                  if (match) navigate(`/topics/${match.topic_id}`);
                }}
              />
            ) : (
              <TopTopicsChart topics={[...topics].sort((a, b) => b.size - a.size)} />
            )}
          </Card>

          <Card size="3">
            <Flex justify="between" align="center" wrap="wrap" gap="3" mb="3">
              <Heading size="4">All Topics ({filtered.length})</Heading>
              {activeGroup ? (
                <Badge size="2" variant="soft" style={{ cursor: 'pointer' }} onClick={() => setGroupFilter(null)}>
                  {activeGroup.label} ✕
                </Badge>
              ) : null}
              <Flex gap="2" align="center">
                <TextField.Root
                  placeholder="Search topics…"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setLimit(TOPIC_PAGE_SIZE);
                  }}
                  style={{ width: 220 }}
                />
                <Select.Root value={sort} onValueChange={(value) => setSort(value as 'size' | 'label')}>
                  <Select.Trigger />
                  <Select.Content>
                    <Select.Item value="size">By size</Select.Item>
                    <Select.Item value="label">By name</Select.Item>
                  </Select.Content>
                </Select.Root>
              </Flex>
            </Flex>
            <Grid columns={{ initial: '1', sm: '2', md: '3' }} gap="4">
              {visible.map((topic) => (
                <Card key={topic.topic_id} size="2" variant="surface">
                  <Heading size="3" mb="1" style={{ textTransform: 'capitalize' }}>
                    <Link to={`/topics/${topic.topic_id}`}>{topic.label}</Link>
                  </Heading>
                  <Text as="p" size="2" color="gray" mb="2">{topic.size.toLocaleString()} bills</Text>
                  <Flex gap="1" wrap="wrap">
                    {topic.top_words.slice(0, 6).map((word) => (
                      <Badge key={word} variant="soft">{word}</Badge>
                    ))}
                  </Flex>
                </Card>
              ))}
            </Grid>
            {filtered.length > limit && (
              <Flex justify="center" mt="4">
                <Text
                  size="2"
                  color="blue"
                  style={{ cursor: 'pointer' }}
                  onClick={() => setLimit((current) => current + TOPIC_PAGE_SIZE)}
                >
                  Show more ({filtered.length - limit} remaining)
                </Text>
              </Flex>
            )}
          </Card>
        </>
      )}

      {subjects && subjects.policy_areas.length > 0 ? (
        <Card size="3">
          <Heading size="4" mb="1">Policy Areas (CRS)</Heading>
          <Text as="p" color="gray" mb="3">
            Bills per Congressional Research Service policy area across {subjects.total_bills.toLocaleString()} tagged bills.
          </Text>
          <PolicyAreaChart areas={subjects.policy_areas} />
        </Card>
      ) : null}

      {subjects && subjects.subjects.length > 0 ? (
        <Card size="3">
          <Heading size="4" mb="1">Legislative Subjects (CRS)</Heading>
          <Text as="p" color="gray" mb="3">
            Most frequent human-annotated subject terms. Click a subject to browse matching bills.
          </Text>
          <Flex gap="1" wrap="wrap">
            {subjects.subjects.map((item) => (
              <Badge key={item.name} variant="soft" asChild>
                <Link to={`/bills?subject=${encodeURIComponent(item.name)}`}>
                  {item.name} · {item.count.toLocaleString()}
                </Link>
              </Badge>
            ))}
          </Flex>
        </Card>
      ) : null}
    </Flex>
  );
}
