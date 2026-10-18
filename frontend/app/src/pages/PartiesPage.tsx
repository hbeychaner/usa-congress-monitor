import { Badge, Box, Callout, Card, Flex, Grid, Heading, Select, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { fetchParties, fetchPartyTopic } from '../api/parties';
import { PARTY_COLORS } from '../components/MemberGraphView';
import { PhraseCloud } from '../components/PhraseCloud';

import type {
  PartiesResponse,
  PartyRanking,
  PartyTopicDetail,
  SubjectUse,
  TermUse,
} from '../api/parties';
import type { PartyGroup } from '../api/graph';

const PARTY_LABELS: Record<PartyGroup, string> = {
  democratic: 'Democratic',
  republican: 'Republican',
  other: 'Other',
};

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function RankingCard({
  ranking,
  selected,
  onSelect,
}: {
  ranking: PartyRanking;
  selected: number | null;
  onSelect: (topicId: number) => void;
}) {
  const max = Math.max(...ranking.topics.map((entry) => entry.bills), 1);
  const color = PARTY_COLORS[ranking.party];
  return (
    <Card size="3">
      <Flex direction="column" gap="3">
        <Flex justify="between" align="baseline">
          <Heading size="4" style={{ color }}>
            {PARTY_LABELS[ranking.party]}
          </Heading>
          <Text size="1" color="gray">
            {ranking.total_bills.toLocaleString()} sponsored bills
          </Text>
        </Flex>
        {ranking.topics.map((entry) => (
          <Flex
            key={entry.topic_id}
            align="center"
            gap="3"
            onClick={() => onSelect(entry.topic_id)}
            style={{
              cursor: 'pointer',
              background: selected === entry.topic_id ? 'var(--gray-3)' : undefined,
              borderRadius: 4,
              padding: '2px 4px',
            }}
          >
            <Box style={{ width: 200, flexShrink: 0, overflow: 'hidden' }}>
              <Text size="2" truncate style={{ textTransform: 'capitalize' }}>
                {entry.label}
              </Text>
            </Box>
            <Box style={{ flex: 1 }}>
              <div
                title={`${entry.bills} bills, ${percent(entry.share_of_topic)} of this topic`}
                style={{
                  width: `${Math.max((entry.bills / max) * 100, 2)}%`,
                  height: 16,
                  background: color,
                  borderRadius: 3,
                }}
              />
            </Box>
            <Box style={{ width: 90, flexShrink: 0, textAlign: 'right' }}>
              <Text size="2" color="gray">
                {entry.bills} · {percent(entry.share_of_topic)}
              </Text>
            </Box>
          </Flex>
        ))}
      </Flex>
    </Card>
  );
}

function SubjectBars({ subjects, color }: { subjects: SubjectUse[]; color: string }) {
  const max = Math.max(...subjects.map((subject) => subject.bills), 1);
  return (
    <Flex direction="column" gap="1">
      {subjects.map((subject) => (
        <Flex key={subject.name} align="center" gap="2">
          <Box style={{ width: 180, flexShrink: 0, overflow: 'hidden' }}>
            <Text size="1" truncate title={subject.name}>
              {subject.name}
            </Text>
          </Box>
          <div
            style={{
              width: `${Math.max((subject.bills / max) * 100, 4)}%`,
              maxWidth: '50%',
              height: 10,
              background: color,
              borderRadius: 2,
            }}
          />
          <Text size="1" color="gray">
            {subject.bills} bills
          </Text>
        </Flex>
      ))}
    </Flex>
  );
}

function Evidence({ use }: { use: TermUse | null }) {
  if (!use) return null;
  return (
    <Box style={{ background: 'var(--gray-2)', borderRadius: 6, padding: 8 }}>
      <Text size="1" color="gray">
        &ldquo;{use.term}&rdquo; appears in {use.bills} bills from {use.sponsors} sponsors, e.g.
      </Text>
      <Flex direction="column">
        {use.examples.map((bill) => (
          <Text size="1" key={bill.doc_id}>
            <Link to={`/bills/${encodeURIComponent(bill.doc_id)}`}>{bill.title}</Link>
          </Text>
        ))}
      </Flex>
    </Box>
  );
}

function GroupLanguage({
  heading,
  color,
  terms,
  subjects,
  summary,
}: {
  heading: string;
  color: string;
  terms: TermUse[];
  subjects: SubjectUse[];
  summary: string;
}) {
  const [picked, setPicked] = useState<TermUse | null>(null);
  const thin = terms.length === 0 && subjects.length === 0;
  return (
    <Flex direction="column" gap="2">
      <Text size="2" weight="bold" style={{ color }}>
        {heading}
      </Text>
      {summary ? <Text size="2">{summary}</Text> : null}
      {thin ? (
        <Text size="2" color="gray">
          Too little distinctive language to draw a conclusion.
        </Text>
      ) : null}
      {subjects.length > 0 ? <SubjectBars subjects={subjects} color={color} /> : null}
      {terms.length > 0 ? (
        <PhraseCloud
          terms={terms}
          color={color}
          selected={picked?.term ?? null}
          onSelect={setPicked}
        />
      ) : null}
      <Evidence use={picked} />
    </Flex>
  );
}

function TopicContrast({ detail }: { detail: PartyTopicDetail }) {
  return (
    <Card size="3">
      <Flex direction="column" gap="4">
        <Flex justify="between" align="baseline" wrap="wrap" gap="2">
          <Heading size="5" style={{ textTransform: 'capitalize' }}>
            <Link to={`/topics/${detail.topic_id}`}>{detail.topic_label}</Link>
          </Heading>
          <Text size="2" color="gray">
            {detail.bills.toLocaleString()} bills in Congress {detail.congress}
          </Text>
        </Flex>
        {detail.party_terms.length === 0 ? (
          <Text size="2" color="gray">
            Too few bills from each party to contrast their language.
          </Text>
        ) : (
          <Grid columns={{ initial: '1', md: '2' }} gap="4">
            {detail.party_terms.map((terms) => (
              <GroupLanguage
                key={terms.party}
                heading={`${PARTY_LABELS[terms.party]} · ${terms.bills} bills`}
                color={PARTY_COLORS[terms.party]}
                terms={terms.terms}
                subjects={terms.subjects}
                summary={terms.summary}
              />
            ))}
          </Grid>
        )}
        {detail.bilateral ? (
          <Flex direction="column" gap="2">
            <Flex gap="2" align="center">
              <Text size="2" weight="bold">
                Bipartisan support
              </Text>
              {detail.bilateral.bilateral ? (
                <Badge color="green">Bilateral Support</Badge>
              ) : (
                <Badge color="gray">Largely partisan</Badge>
              )}
              <Text size="2" color="gray">
                {detail.bilateral.bipartisan_bills} of {detail.bilateral.bills} bills (
                {percent(detail.bilateral.share)})
              </Text>
            </Flex>
            <GroupLanguage
              heading="What the bipartisan bills share"
              color="var(--green-11)"
              terms={detail.bilateral.terms}
              subjects={detail.bilateral.subjects}
              summary={detail.bilateral.summary}
            />
          </Flex>
        ) : null}
        {detail.perspectives.length > 0 ? (
          <Flex direction="column" gap="2">
            <Text size="2" weight="bold">
              Perspectives
            </Text>
            <Grid columns={{ initial: '1', md: '2' }} gap="3">
              {detail.perspectives.map((perspective) => (
                <Card key={perspective.label}>
                  <Flex direction="column" gap="1">
                    <Text size="2" weight="bold">
                      {perspective.label} · {perspective.size} bills
                    </Text>
                    <Text size="1" color="gray">
                      {perspective.parties
                        .map((party) => `${PARTY_LABELS[party.party]} ${percent(party.share)}`)
                        .join(' · ')}
                    </Text>
                    <Text size="2">{perspective.terms.join(', ')}</Text>
                  </Flex>
                </Card>
              ))}
            </Grid>
          </Flex>
        ) : null}
      </Flex>
    </Card>
  );
}

export function PartiesPage() {
  const [data, setData] = useState<PartiesResponse | null>(null);
  const [congress, setCongress] = useState<number | undefined>(undefined);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<PartyTopicDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setSelected(null);
    fetchParties(congress)
      .then((response) => {
        setData(response);
        setSelected(response.parties[0]?.topics[0]?.topic_id ?? null);
      })
      .catch((err) => setError((err as Error).message));
  }, [congress]);

  useEffect(() => {
    if (!data?.congress || selected === null) {
      setDetail(null);
      return;
    }
    fetchPartyTopic(data.congress, selected)
      .then((response) => setDetail(response.topic))
      .catch(() => setDetail(null));
  }, [data?.congress, selected]);

  if (error) {
    return (
      <Callout.Root color="red">
        <Callout.Text>{error}</Callout.Text>
      </Callout.Root>
    );
  }
  if (!data) return <Text>Loading…</Text>;
  if (data.congress === null) {
    return (
      <Callout.Root>
        <Callout.Text>No party analysis has been built yet.</Callout.Text>
      </Callout.Root>
    );
  }

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="center" wrap="wrap" gap="3">
        <Heading size="7">Parties</Heading>
        <Select.Root
          value={String(data.congress)}
          onValueChange={(value) => setCongress(Number(value))}
        >
          <Select.Trigger />
          <Select.Content>
            {data.congresses.map((value) => (
              <Select.Item key={value} value={String(value)}>
                Congress {value}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>
      <Text size="2" color="gray">
        Topics each party sponsors most, and the language that sets each party&apos;s bills apart.
        Procedural measures are excluded.
      </Text>
      <Grid columns={{ initial: '1', md: '2' }} gap="4">
        {data.parties.map((ranking) => (
          <RankingCard
            key={ranking.party}
            ranking={ranking}
            selected={selected}
            onSelect={setSelected}
          />
        ))}
      </Grid>
      {detail ? <TopicContrast detail={detail} /> : null}
      <Card size="3">
        <Flex direction="column" gap="3">
          <Heading size="4">Bilateral Support</Heading>
          <Text size="2" color="gray">
            Topics where a large share of bills carry cosponsors from the other party.
          </Text>
          {data.bilateral.length === 0 ? (
            <Text size="2" color="gray">
              No topics meet the threshold.
            </Text>
          ) : (
            data.bilateral.map((entry) => (
              <Flex
                key={entry.topic_id}
                direction="column"
                gap="1"
                onClick={() => setSelected(entry.topic_id)}
                style={{ cursor: 'pointer' }}
              >
                <Flex gap="3" align="baseline">
                  <Text size="2" weight="bold" style={{ textTransform: 'capitalize' }}>
                    {entry.label}
                  </Text>
                  <Badge color="green">{percent(entry.share)} bipartisan</Badge>
                  <Text size="1" color="gray">
                    {entry.bipartisan_bills} of {entry.bills} bills
                  </Text>
                </Flex>
                {entry.summary ? <Text size="2">{entry.summary}</Text> : null}
              </Flex>
            ))
          )}
        </Flex>
      </Card>
    </Flex>
  );
}
