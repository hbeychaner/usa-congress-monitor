import { Avatar, Badge, Button, Card, DataList, Flex, Heading, Progress, SegmentedControl, Table, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  fetchMemberActivity,
  fetchMemberProfile,
  type MemberActivityResponse,
  type MemberProfileResponse,
} from '../api/members';
import { fetchMemberTopics, type MemberTopicsResponse } from '../api/topics';

const PARTY_COLORS: Record<string, 'blue' | 'red' | 'gray'> = {
  Democratic: 'blue',
  Republican: 'red',
};

const DOC_TYPE_LABELS: Record<string, string> = {
  bill: 'Bills',
  amendment: 'Amendments',
};

const ACTIVITY_PAGE_SIZE = 25;

function formatDate(value: string | null | undefined): string {
  if (!value) return 'No date';
  return value.slice(0, 10);
}

export function MemberProfilePage() {
  const { bioguideId = '' } = useParams();
  const [profile, setProfile] = useState<MemberProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activity, setActivity] = useState<MemberActivityResponse | null>(null);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityType, setActivityType] = useState('all');
  const [activityPage, setActivityPage] = useState(1);
  const [memberTopics, setMemberTopics] = useState<MemberTopicsResponse | null>(null);

  useEffect(() => {
    setMemberTopics(null);
    fetchMemberTopics(bioguideId)
      .then(setMemberTopics)
      .catch(() => setMemberTopics(null));
  }, [bioguideId]);

  useEffect(() => {
    setActivityLoading(true);
    fetchMemberActivity(
      bioguideId,
      activityPage,
      ACTIVITY_PAGE_SIZE,
      activityType === 'all' ? undefined : activityType,
    )
      .then((data) => setActivity(data))
      .catch(() => setActivity(null))
      .finally(() => setActivityLoading(false));
  }, [bioguideId, activityType, activityPage]);

  useEffect(() => {
    fetchMemberProfile(bioguideId)
      .then((data) => setProfile(data))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [bioguideId]);

  if (loading) {
    return <Text as="p">Loading member profile...</Text>;
  }

  if (error || !profile) {
    return <Text as="p">Failed to load member profile: {error ?? 'Unknown error'}</Text>;
  }

  const member = profile.member;
  const terms = [...(member.terms ?? [])].sort((a, b) => (b.congress ?? 0) - (a.congress ?? 0));
  const leadership = member.leadership ?? [];

  const activityByType = profile.recent_activity.reduce<Record<string, number>>((acc, item) => {
    acc[item.activity_type] = (acc[item.activity_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Flex direction="column" gap="5">
      <Card size="4">
        <Flex gap="4" align="center" wrap="wrap">
          <Avatar
            size="7"
            radius="full"
            src={member.image_url ?? undefined}
            fallback={member.display_name.charAt(0)}
          />
          <Flex direction="column" gap="2">
            <Heading size="7">{member.honorific_name ? `${member.honorific_name} ` : ''}{member.display_name}</Heading>
            <Text color="gray">{member.chamber ?? 'Chamber unavailable'} · {member.state}</Text>
            {member.birth_year ? (
              <Text size="2" color="gray">
                Born {member.birth_year}{member.death_year ? ` · Died ${member.death_year}` : ''}
              </Text>
            ) : null}
            <Flex gap="2" wrap="wrap" align="center">
              <Badge color={PARTY_COLORS[member.party] ?? 'gray'}>{member.party}</Badge>
              {member.current_member != null ? (
                <Badge color={member.current_member ? 'green' : 'gray'} variant="soft">
                  {member.current_member ? 'Currently serving' : 'Former member'}
                </Badge>
              ) : null}
              {member.district != null ? <Badge variant="soft">District: {member.district}</Badge> : null}
              {member.term_start_year != null ? (
                <Badge variant="soft">
                  Term: {member.term_start_year}–{member.term_end_year ?? 'present'}
                </Badge>
              ) : null}
              <Badge variant="soft">Bioguide: {member.bioguide_id}</Badge>
            </Flex>
          </Flex>
        </Flex>
      </Card>

      {member.official_website_url || member.office_address || member.phone_number ? (
        <Card size="3">
          <Heading size="4" mb="2">Contact</Heading>
          <DataList.Root>
            {member.official_website_url ? (
              <DataList.Item>
                <DataList.Label>Official website</DataList.Label>
                <DataList.Value>
                  <a href={member.official_website_url} target="_blank" rel="noreferrer">{member.official_website_url}</a>
                </DataList.Value>
              </DataList.Item>
            ) : null}
            {member.office_address ? (
              <DataList.Item>
                <DataList.Label>Office</DataList.Label>
                <DataList.Value>{member.office_address}</DataList.Value>
              </DataList.Item>
            ) : null}
            {member.phone_number ? (
              <DataList.Item>
                <DataList.Label>Phone</DataList.Label>
                <DataList.Value>{member.phone_number}</DataList.Value>
              </DataList.Item>
            ) : null}
          </DataList.Root>
        </Card>
      ) : null}

      {leadership.length > 0 ? (
        <Card size="3">
          <Heading size="4" mb="2">Leadership</Heading>
          <Flex direction="column" gap="1">
            {leadership.map((role, index) => (
              <Text as="p" key={index}>
                {String((role as Record<string, unknown>).type ?? 'Leadership role')}
                {(role as Record<string, unknown>).congress ? ` · Congress ${String((role as Record<string, unknown>).congress)}` : ''}
              </Text>
            ))}
          </Flex>
        </Card>
      ) : null}

      {terms.length > 0 ? (
        <Card size="3">
          <Heading size="4" mb="2">Service History</Heading>
          <Table.Root size="1">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Congress</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Chamber</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Years</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>State</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {terms.map((term, index) => (
                <Table.Row key={`${term.congress ?? index}-${term.chamber ?? ''}`}>
                  <Table.Cell>{term.congress ?? '—'}</Table.Cell>
                  <Table.Cell>{term.chamber ?? '—'}</Table.Cell>
                  <Table.Cell>{term.start_year ?? '?'}–{term.end_year ?? 'present'}</Table.Cell>
                  <Table.Cell>{term.state_name ?? term.state_code ?? '—'}{term.district != null ? ` (District ${term.district})` : ''}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Card>
      ) : null}

      <Card size="3">
        <Heading size="4" mb="2">Activity Breakdown</Heading>
        <Flex gap="2" wrap="wrap">
          {Object.entries(activityByType).map(([activityType, count]) => (
            <Badge key={activityType} variant="soft">{activityType}: {count}</Badge>
          ))}
        </Flex>
      </Card>

      <Card size="3">
        <Heading size="4" mb="2">Legislative Topics</Heading>
        <Flex direction="column" gap="3">
          {profile.topics.length > 0 ? (
            <Flex direction="column" gap="2">
              {profile.topics.map((topic) => (
                <Flex key={topic.label} align="center" gap="2">
                  <Text size="2" style={{ width: 220, textTransform: 'capitalize' }}>{topic.label}</Text>
                  <div style={{ flex: 1 }}>
                    <Progress value={Math.round(topic.weight * 100)} />
                  </div>
                  <Text size="1" color="gray" style={{ width: 40, textAlign: 'right' }}>
                    {Math.round(topic.weight * 100)}%
                  </Text>
                </Flex>
              ))}
            </Flex>
          ) : (
            <Text as="p" color="gray">No modeled topic assignments yet — topics appear after the topic model is trained.</Text>
          )}
          {memberTopics && memberTopics.subjects.length > 0 ? (
              <Flex direction="column" gap="1">
                <Heading size="3" mt="2">CRS Subjects</Heading>
                <Flex gap="1" wrap="wrap">
                  {memberTopics.subjects.map((subject) => (
                    <Badge key={subject.label} variant="soft" asChild>
                      <Link to={`/bills?subject=${encodeURIComponent(subject.label)}`}>
                        {subject.label} · {Math.round(subject.weight * 100)}%
                      </Link>
                    </Badge>
                  ))}
                </Flex>
              </Flex>
            ) : null}
            {memberTopics && memberTopics.trend.length > 0 ? (
              <Flex direction="column" gap="1">
                <Heading size="3" mt="2">Topics Over Time</Heading>
                {Object.entries(
                  memberTopics.trend.reduce<Record<string, typeof memberTopics.trend>>((acc, point) => {
                    (acc[point.period] ??= []).push(point);
                    return acc;
                  }, {}),
                ).map(([period, points]) => (
                  <Flex key={period} align="center" gap="2" wrap="wrap">
                    <Text size="1" weight="bold" style={{ width: 70 }}>{period}</Text>
                    {points
                      .sort((a, b) => b.count - a.count)
                      .slice(0, 6)
                      .map((point) => (
                        <Badge key={`${period}:${point.topic_id}`} variant="soft" style={{ textTransform: 'capitalize' }} asChild>
                          <Link to={`/topics/${point.topic_id}`}>{point.label} × {point.count}</Link>
                        </Badge>
                      ))}
                  </Flex>
                ))}
              </Flex>
            ) : null}
        </Flex>
      </Card>

      <Card size="3">
        <Heading size="4" mb="2">Recent Activity</Heading>
        {profile.recent_activity.length > 0 ? (
          <Flex direction="column" gap="2">
            {profile.recent_activity.map((item) => (
              <Text as="p" key={`${item.bill_id}:${item.activity_type}`}>
                <Text weight="bold">{item.activity_type}</Text>: {item.title} (
                <Link to={`/bills/${encodeURIComponent(item.bill_id)}`}>{item.bill_id}</Link>)
              </Text>
            ))}
          </Flex>
        ) : <Text as="p" color="gray">No indexed bill activity for this member.</Text>}
      </Card>

      <Card size="3">
        <Flex justify="between" align="center" mb="2" wrap="wrap" gap="2">
          <Heading size="4">All Activity</Heading>
          <SegmentedControl.Root
            value={activityType}
            onValueChange={(value) => {
              setActivityType(value);
              setActivityPage(1);
            }}
          >
            <SegmentedControl.Item value="all">All</SegmentedControl.Item>
            <SegmentedControl.Item value="bill">Bills</SegmentedControl.Item>
            <SegmentedControl.Item value="amendment">Amendments</SegmentedControl.Item>
          </SegmentedControl.Root>
        </Flex>
        {activity ? (
          <Flex gap="2" wrap="wrap" mb="3">
            {Object.entries(activity.counts).map(([docType, count]) => (
              <Badge key={docType} variant="soft">
                {DOC_TYPE_LABELS[docType] ?? docType}: {count.toLocaleString()}
              </Badge>
            ))}
          </Flex>
        ) : null}
        {activityLoading ? (
          <Text as="p" color="gray">Loading activity...</Text>
        ) : activity && activity.items.length > 0 ? (
          <Flex direction="column" gap="2">
            {activity.items.map((item) => (
              <Flex key={`${item.document_type}:${item.id}`} gap="2" align="center" wrap="wrap">
                <Badge color={item.document_type === 'bill' ? 'blue' : 'orange'} variant="soft">
                  {DOC_TYPE_LABELS[item.document_type] ?? item.document_type}
                </Badge>
                <Badge variant="outline">{item.activity_type}</Badge>
                <Text size="1" color="gray">{formatDate(item.date)}</Text>
                {item.bill_id ? (
                  <Link to={`/bills/${encodeURIComponent(item.bill_id)}`}>{item.title}</Link>
                ) : (
                  <Text>{item.title}</Text>
                )}
              </Flex>
            ))}
            <Flex gap="2" align="center" mt="2">
              <Button
                variant="soft"
                disabled={activityPage <= 1}
                onClick={() => setActivityPage((page) => Math.max(1, page - 1))}
              >
                Previous
              </Button>
              <Text size="1" color="gray">
                Page {activity.page} of {Math.max(1, Math.ceil(activity.total / ACTIVITY_PAGE_SIZE))}
              </Text>
              <Button
                variant="soft"
                disabled={activityPage * ACTIVITY_PAGE_SIZE >= activity.total}
                onClick={() => setActivityPage((page) => page + 1)}
              >
                Next
              </Button>
            </Flex>
          </Flex>
        ) : (
          <Text as="p" color="gray">No indexed activity for this member.</Text>
        )}
      </Card>

      <Card size="3">
        <Heading size="4" mb="2">Topic Profile</Heading>
        {profile.topics.length > 0 ? (
          <Flex direction="column" gap="3">
            {profile.topics.map((topic) => (
              <Flex direction="column" gap="1" key={topic.label}>
                <Flex justify="between">
                  <Text>{topic.label}</Text>
                  <Text weight="bold">{Math.round(topic.weight * 100)}%</Text>
                </Flex>
                <Progress value={Math.round(topic.weight * 100)} />
              </Flex>
            ))}
          </Flex>
        ) : <Text as="p" color="gray">No indexed topic associations for this member.</Text>}
      </Card>
    </Flex>
  );
}
