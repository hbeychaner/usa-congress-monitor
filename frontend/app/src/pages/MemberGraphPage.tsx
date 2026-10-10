import { Badge, Button, Callout, Card, Checkbox, Flex, Heading, SegmentedControl, Select, Slider, Text, TextField } from '@radix-ui/themes';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { fetchNeighborhood, type Neighborhood, type PartyGroup } from '../api/graph';
import { fetchMembers, type MemberSummary } from '../api/members';
import { MemberGraphView, METASUBJECT_PREFIX, PARTY_COLORS, SUBJECT_PREFIX, TOPIC_PREFIX, type ColorMode } from '../components/MemberGraphView';

const MAX_SEEDS = 5;
const CONGRESSES = [119, 118, 117, 116, 115, 114, 113];
const PARTIES: { value: PartyGroup; label: string }[] = [
  { value: 'democratic', label: 'Democratic' },
  { value: 'republican', label: 'Republican' },
  { value: 'other', label: 'Other' },
];

type WeightSliderProps = { label: string; value: number; onCommit: (value: number) => void };

function WeightSlider({ label, value, onCommit }: WeightSliderProps) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <Flex direction="column" gap="1" style={{ minWidth: 180 }}>
      <Text size="2" weight="medium">{label}: {draft.toFixed(2)}</Text>
      <Slider min={0} max={1} step={0.05} value={[draft]} onValueChange={([next]) => setDraft(next)} onValueCommit={([next]) => onCommit(next)} />
    </Flex>
  );
}

export function MemberGraphPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const seeds = searchParams.getAll('member');
  const [collaborationWeight, setCollaborationWeight] = useState(1);
  const [votingWeight, setVotingWeight] = useState(0.6);
  const [topicWeight, setTopicWeight] = useState(0.3);
  const [congress, setCongress] = useState<number | null>(null);
  const [chamber, setChamber] = useState<'house' | 'senate' | null>(null);
  const [parties, setParties] = useState<PartyGroup[]>([]);
  const [limit, setLimit] = useState(15);
  const [showTopics, setShowTopics] = useState(false);
  const [showSubjects, setShowSubjects] = useState(false);
  const [showMetasubjects, setShowMetasubjects] = useState(false);
  const [colorMode, setColorMode] = useState<ColorMode>('party');
  const [data, setData] = useState<Neighborhood | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MemberSummary[]>([]);

  const seedKey = seeds.join(',');
  useEffect(() => {
    if (!seeds.length) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchNeighborhood({ members: seeds, collaborationWeight, votingWeight, topicWeight, congress, chamber, parties, limit, includeTopics: showTopics, includeSubjects: showSubjects, includeMetasubjects: showMetasubjects })
      .then((response) => {
        if (cancelled) return;
        setData(response);
        setError(null);
        setSelectedId(null);
      })
      .catch((err: Error) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedKey, collaborationWeight, votingWeight, topicWeight, congress, chamber, parties, limit, showTopics, showSubjects, showMetasubjects]);

  const names = useMemo(
    () => new Map((data?.nodes ?? []).map((node) => [node.member.bioguide_id, node.member.display_name])),
    [data],
  );
  const selected = data?.nodes?.find((node) => node.member.bioguide_id === selectedId) ?? null;
  const selectedTopic = selectedId?.startsWith(TOPIC_PREFIX)
    ? data?.topic_nodes?.find((topic) => `${TOPIC_PREFIX}${topic.topic_id}` === selectedId) ?? null
    : null;
  const topicMembers = useMemo(
    () => (data?.topic_links ?? [])
      .filter((link) => link.topic_id === selectedTopic?.topic_id)
      .sort((a, b) => b.bills - a.bills),
    [data, selectedTopic],
  );
  const selectedSubject = selectedId?.startsWith(SUBJECT_PREFIX)
    ? data?.subject_nodes?.find((subject) => `${SUBJECT_PREFIX}${subject.name}` === selectedId) ?? null
    : null;
  const subjectMembers = useMemo(
    () => (data?.subject_links ?? [])
      .filter((link) => link.subject === selectedSubject?.name)
      .sort((a, b) => b.bills - a.bills),
    [data, selectedSubject],
  );
  const memberSubjects = useMemo(
    () => (data?.subject_links ?? []).filter((link) => link.member === selectedId),
    [data, selectedId],
  );
  const selectedMetasubject = selectedId?.startsWith(METASUBJECT_PREFIX)
    ? data?.metasubject_nodes?.find((group) => `${METASUBJECT_PREFIX}${group.metasubject_id}` === selectedId) ?? null
    : null;
  const metasubjectMembers = useMemo(
    () => (data?.metasubject_links ?? [])
      .filter((link) => link.metasubject_id === selectedMetasubject?.metasubject_id)
      .sort((a, b) => b.bills - a.bills),
    [data, selectedMetasubject],
  );
  const memberMetasubjects = useMemo(() => {
    const names = new Map((data?.metasubject_nodes ?? []).map((group) => [group.metasubject_id, group.name]));
    return (data?.metasubject_links ?? [])
      .filter((link) => link.member === selectedId)
      .map((link) => ({ name: names.get(link.metasubject_id) ?? String(link.metasubject_id), bills: link.bills }));
  }, [data, selectedId]);
  const memberTopics = useMemo(() => {
    const labels = new Map((data?.topic_nodes ?? []).map((topic) => [topic.topic_id, topic.label]));
    return (data?.topic_links ?? [])
      .filter((link) => link.member === selectedId)
      .map((link) => ({ label: labels.get(link.topic_id) ?? String(link.topic_id), bills: link.bills }));
  }, [data, selectedId]);
  const selectedLinks = useMemo(
    () => (data?.links ?? []).filter((link) => link.source === selectedId || link.target === selectedId).slice(0, 8),
    [data, selectedId],
  );

  function setSeeds(next: string[]) {
    setSearchParams(next.length ? { member: next } : {});
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setResults((await fetchMembers(1, 10, { query })).members);
  }

  function toggleParty(party: PartyGroup, checked: boolean) {
    setParties(checked ? [...parties, party] : parties.filter((entry) => entry !== party));
  }

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="end" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Relationships</Text>
          <Heading size="7">Member graph</Heading>
          <Text color="gray">Who works with, and votes like, a member. Edges blend cosponsorship, roll-call agreement and shared legislative topics.</Text>
        </Flex>
        <Flex gap="3" align="center">
          <SegmentedControl.Root size="1" value={colorMode} onValueChange={(value) => setColorMode(value as ColorMode)}>
            <SegmentedControl.Item value="party">Party</SegmentedControl.Item>
            <SegmentedControl.Item value="community">Communities</SegmentedControl.Item>
          </SegmentedControl.Root>
          {colorMode === 'party' ? PARTIES.map((party) => (
            <Flex key={party.value} gap="1" align="center">
              <span style={{ width: 10, height: 10, borderRadius: 5, background: PARTY_COLORS[party.value] }} />
              <Text size="1" color="gray">{party.label}</Text>
            </Flex>
          )) : <Text size="1" color="gray">Colors mark clusters of closely connected members</Text>}
        </Flex>
      </Flex>

      <Card size="3">
        <Flex direction="column" gap="4">
          <Flex gap="3" wrap="wrap" align="end">
            <form onSubmit={search}>
              <Flex gap="2" align="end">
                <label>
                  <Text as="div" size="2" mb="1" weight="medium">Add member</Text>
                  <TextField.Root value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or Bioguide ID" />
                </label>
                <Button type="submit" variant="soft">Search</Button>
              </Flex>
            </form>
            {seeds.map((seed) => (
              <Badge key={seed} size="2" variant="soft">
                {names.get(seed) ?? seed}
                <Button size="1" variant="ghost" onClick={() => setSeeds(seeds.filter((entry) => entry !== seed))}>x</Button>
              </Badge>
            ))}
          </Flex>
          {results.length ? (
            <Flex gap="2" wrap="wrap">
              {results.map((member) => (
                <Button
                  key={member.bioguide_id}
                  size="1"
                  variant="outline"
                  disabled={seeds.includes(member.bioguide_id) || seeds.length >= MAX_SEEDS}
                  onClick={() => { setSeeds([...seeds, member.bioguide_id]); setResults([]); setQuery(''); }}
                >
                  {member.display_name} ({member.party[0]}-{member.state})
                </Button>
              ))}
            </Flex>
          ) : null}
          <Flex gap="5" wrap="wrap" align="end">
            <WeightSlider label="Collaboration" value={collaborationWeight} onCommit={setCollaborationWeight} />
            <WeightSlider label="Voting" value={votingWeight} onCommit={setVotingWeight} />
            <WeightSlider label="Topics" value={topicWeight} onCommit={setTopicWeight} />
            <Flex direction="column" gap="1" style={{ minWidth: 160 }}>
              <Text size="2" weight="medium">Neighbors per member: {limit}</Text>
              <Slider min={5} max={40} step={1} defaultValue={[limit]} onValueCommit={([next]) => setLimit(next)} />
            </Flex>
            <Flex direction="column" gap="1">
              <Text size="2" weight="medium">Congress</Text>
              <Select.Root value={congress ? String(congress) : 'all'} onValueChange={(value) => setCongress(value === 'all' ? null : Number(value))}>
                <Select.Trigger />
                <Select.Content>
                  <Select.Item value="all">All (113th+)</Select.Item>
                  {CONGRESSES.map((entry) => <Select.Item key={entry} value={String(entry)}>{entry}th</Select.Item>)}
                </Select.Content>
              </Select.Root>
            </Flex>
            <Flex direction="column" gap="1">
              <Text size="2" weight="medium">Chamber</Text>
              <Select.Root value={chamber ?? 'all'} onValueChange={(value) => setChamber(value === 'all' ? null : (value as 'house' | 'senate'))}>
                <Select.Trigger />
                <Select.Content>
                  <Select.Item value="all">Both</Select.Item>
                  <Select.Item value="house">House</Select.Item>
                  <Select.Item value="senate">Senate</Select.Item>
                </Select.Content>
              </Select.Root>
            </Flex>
            <Flex gap="3" align="center">
              <Text as="label" size="2">
                <Flex gap="1" align="center">
                  <Checkbox checked={showTopics} onCheckedChange={(checked) => setShowTopics(checked === true)} />
                  Show topics
                </Flex>
              </Text>
              <Text as="label" size="2">
                <Flex gap="1" align="center">
                  <Checkbox checked={showSubjects} onCheckedChange={(checked) => setShowSubjects(checked === true)} />
                  Show subjects
                </Flex>
              </Text>
              <Text as="label" size="2">
                <Flex gap="1" align="center">
                  <Checkbox checked={showMetasubjects} onCheckedChange={(checked) => setShowMetasubjects(checked === true)} />
                  Show metasubjects
                </Flex>
              </Text>
              {PARTIES.map((party) => (
                <Text key={party.value} as="label" size="2">
                  <Flex gap="1" align="center">
                    <Checkbox checked={parties.includes(party.value)} onCheckedChange={(checked) => toggleParty(party.value, checked === true)} />
                    {party.label}
                  </Flex>
                </Text>
              ))}
            </Flex>
          </Flex>
        </Flex>
      </Card>

      {error ? <Callout.Root color="red"><Callout.Text>{error}</Callout.Text></Callout.Root> : null}

      <Flex gap="4" wrap="wrap" align="start">
        <Card size="2" style={{ flex: '1 1 600px', minWidth: 0 }}>
          {!seeds.length ? (
            <Text color="gray">Search for a member to start exploring their network.</Text>
          ) : data && data.nodes?.length ? (
            <MemberGraphView data={data} selectedId={selectedId} colorMode={colorMode} onSelect={setSelectedId} />
          ) : (
            <Text color="gray">{loading ? 'Loading graph...' : 'No connections match these filters.'}</Text>
          )}
        </Card>
        {selected ? (
          <Card size="3" style={{ flex: '0 0 300px' }}>
            <Flex direction="column" gap="2">
              <Heading size="4">{selected.member.display_name}</Heading>
              <Flex gap="2">
                <Badge color={selected.party_group === 'democratic' ? 'blue' : selected.party_group === 'republican' ? 'red' : 'gray'}>{selected.member.party}</Badge>
                <Badge variant="soft">{selected.member.state}</Badge>
                {selected.member.chamber ? <Badge variant="soft">{selected.member.chamber}</Badge> : null}
              </Flex>
              <Flex gap="2" wrap="wrap">
                <Button size="1" onClick={() => setSeeds([selected.member.bioguide_id])}>Center here</Button>
                <Button size="1" variant="soft" disabled={seeds.includes(selected.member.bioguide_id) || seeds.length >= MAX_SEEDS} onClick={() => setSeeds([...seeds, selected.member.bioguide_id])}>Add as seed</Button>
                <Button size="1" variant="outline" asChild><Link to={`/members/${selected.member.bioguide_id}`}>Profile</Link></Button>
              </Flex>
              {memberTopics.length ? (
                <>
                  <Text size="2" weight="bold" mt="2">Top topics (sponsored bills)</Text>
                  {memberTopics.map((topic) => <Text key={topic.label} size="2">{topic.label} ({topic.bills})</Text>)}
                </>
              ) : null}
              {memberMetasubjects.length ? (
                <>
                  <Text size="2" weight="bold" mt="2">Top metasubjects (sponsored bills)</Text>
                  {memberMetasubjects.map((group) => <Text key={group.name} size="2">{group.name} ({group.bills})</Text>)}
                </>
              ) : null}
              {memberSubjects.length ? (
                <>
                  <Text size="2" weight="bold" mt="2">Top subjects (sponsored bills)</Text>
                  {memberSubjects.map((link) => <Text key={link.subject} size="2">{link.subject} ({link.bills})</Text>)}
                </>
              ) : null}
              <Text size="2" weight="bold" mt="2">Strongest links</Text>
              {selectedLinks.map((link) => {
                const other = link.source === selectedId ? link.target : link.source;
                const signals = link.signal_scores ?? {};
                return (
                  <Text key={other} size="2">
                    {names.get(other) ?? other}: {link.score.toFixed(2)}
                    <Text size="1" color="gray"> (collab {(signals.collaboration ?? 0).toFixed(2)}, votes {(signals.voting ?? 0).toFixed(2)}, topics {(signals.topic ?? 0).toFixed(2)})</Text>
                    {link.shared_topics?.length ? <Text as="div" size="1" color="gray">Shared: {link.shared_topics.join('; ')}</Text> : null}
                  </Text>
                );
              })}
            </Flex>
          </Card>
        ) : selectedMetasubject ? (
          <Card size="3" style={{ flex: '0 0 300px' }}>
            <Flex direction="column" gap="2">
              <Heading size="4">{selectedMetasubject.name}</Heading>
              <Text size="2" weight="bold" mt="2">Members sponsoring in it (bills)</Text>
              {metasubjectMembers.map((link) => (
                <Text key={link.member} size="2">
                  <Link to={`/members/${link.member}`}>{names.get(link.member) ?? link.member}</Link> ({link.bills})
                </Text>
              ))}
            </Flex>
          </Card>
        ) : selectedSubject ? (
          <Card size="3" style={{ flex: '0 0 300px' }}>
            <Flex direction="column" gap="2">
              <Heading size="4">{selectedSubject.name}</Heading>
              <Text size="2" weight="bold" mt="2">Members sponsoring on it (bills)</Text>
              {subjectMembers.map((link) => (
                <Text key={link.member} size="2">
                  <Link to={`/members/${link.member}`}>{names.get(link.member) ?? link.member}</Link> ({link.bills})
                </Text>
              ))}
            </Flex>
          </Card>
        ) : selectedTopic ? (
          <Card size="3" style={{ flex: '0 0 300px' }}>
            <Flex direction="column" gap="2">
              <Heading size="4">{selectedTopic.label}</Heading>
              <Button size="1" variant="outline" asChild><Link to={`/topics/${selectedTopic.topic_id}`}>Open topic</Link></Button>
              <Text size="2" weight="bold" mt="2">Members working on it (sponsored bills)</Text>
              {topicMembers.map((link) => (
                <Text key={link.member} size="2">
                  <Link to={`/members/${link.member}`}>{names.get(link.member) ?? link.member}</Link> ({link.bills})
                </Text>
              ))}
            </Flex>
          </Card>
        ) : null}
      </Flex>
    </Flex>
  );
}
