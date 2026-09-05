import { Card, Flex, Grid, Heading, Text, TextField } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchStateTimeline, type StateTimelineResponse, type TimelineMember } from '../api/states';

function partyClass(party: string): string {
  const normalized = party.toLowerCase();
  return normalized === 'democratic' ? 'democrat' : normalized;
}

function ChamberSection({ title, members }: { title: string; members: TimelineMember[] }) {
  return (
    <section className="chamber-section">
      <Heading size="4" mb="2">{title}</Heading>
      {members.length === 0 ? (
        <Text as="p" color="gray">No members in selected range.</Text>
      ) : (
        <ul className="timeline-group-members">
          {members.map((member) => (
            <li key={`${member.bioguide_id}-${member.congress_start}`} className="timeline-item">
              <article className="timeline-card">
                <div className="timeline-card-top"><span className={`party-dot party-dot-${partyClass(member.party)}`} aria-hidden="true" /><span className="chip">{member.congress_start}-{member.congress_end}</span></div>
                <h3><Link to={`/members/${member.bioguide_id}`}>{member.name}</Link></h3>
                <p>{member.party} · Bioguide {member.bioguide_id}</p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function StateDetailPage() {
  const { stateCode = '' } = useParams();
  const [timeline, setTimeline] = useState<StateTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCongress, setFromCongress] = useState<number>(116);
  const [toCongress, setToCongress] = useState<number>(119);

  useEffect(() => {
    setLoading(true);
    fetchStateTimeline(stateCode, { fromCongress, toCongress })
      .then((data) => setTimeline(data))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [stateCode, fromCongress, toCongress]);

  if (loading) {
    return <Text as="p">Loading timeline...</Text>;
  }

  if (error || !timeline) {
    return <Text as="p">Failed to load timeline: {error ?? 'Unknown error'}</Text>;
  }

  const houseGroups = timeline.house.groups ?? [];
  const senateGroups = timeline.senate.groups ?? [];
  const congresses = [...new Set([
    ...houseGroups.map((group) => group.congress),
    ...senateGroups.map((group) => group.congress),
  ])].sort((left, right) => right - left);
  const houseByCongress = new Map(houseGroups.map((group) => [group.congress, group.members]));
  const senateByCongress = new Map(senateGroups.map((group) => [group.congress, group.members]));

  return (
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="7">{timeline.state_name} ({timeline.state_code})</Heading>
        <Text color="gray">Delegations grouped by Congress from OpenSearch member records.</Text>
      </Flex>

      <Card size="3">
        <Heading size="4" mb="2">Timeline Filters</Heading>
        <Flex gap="4" wrap="wrap">
          <label>
            <Text as="div" size="2" mb="1" weight="medium">From Congress</Text>
            <TextField.Root
              type="number"
              value={fromCongress}
              min={1}
              onChange={(event) => setFromCongress(Number(event.target.value || 1))}
            />
          </label>
          <label>
            <Text as="div" size="2" mb="1" weight="medium">To Congress</Text>
            <TextField.Root
              type="number"
              value={toCongress}
              min={1}
              onChange={(event) => setToCongress(Number(event.target.value || 1))}
            />
          </label>
        </Flex>
      </Card>

      <Grid columns={{ initial: '1', sm: '2' }} gap="4">
        <Card size="3">
          <Heading size="4" mb="1">House Seats</Heading>
          <Text as="p" color="gray">{timeline.house.members.length} matching timeline entries</Text>
        </Card>
        <Card size="3">
          <Heading size="4" mb="1">Senate Seats</Heading>
          <Text as="p" color="gray">{timeline.senate.members.length} matching timeline entries</Text>
        </Card>
      </Grid>

      <div className="timeline-grid congress-grid">
        {congresses.map((congress) => (
          <section className="timeline-lane congress-column" key={congress}>
            <Heading size="5" mb="2">Congress {congress}</Heading>
            <ChamberSection title="House" members={houseByCongress.get(congress) ?? []} />
            <ChamberSection title="Senate" members={senateByCongress.get(congress) ?? []} />
          </section>
        ))}
      </div>
    </Flex>
  );
}
