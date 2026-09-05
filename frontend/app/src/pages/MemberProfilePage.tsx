import { Avatar, Badge, Card, Flex, Heading, Progress, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchMemberProfile, type MemberProfileResponse } from '../api/members';

const PARTY_COLORS: Record<string, 'blue' | 'red' | 'gray'> = {
  Democratic: 'blue',
  Republican: 'red',
};

export function MemberProfilePage() {
  const { bioguideId = '' } = useParams();
  const [profile, setProfile] = useState<MemberProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
            src={profile.member.image_url ?? undefined}
            fallback={profile.member.display_name.charAt(0)}
          />
          <Flex direction="column" gap="2">
            <Heading size="7">{profile.member.display_name}</Heading>
            <Text color="gray">{profile.member.chamber ?? 'Chamber unavailable'} · {profile.member.state}</Text>
            <Flex gap="2" wrap="wrap" align="center">
              <Badge color={PARTY_COLORS[profile.member.party] ?? 'gray'}>{profile.member.party}</Badge>
              {profile.member.district != null ? <Badge variant="soft">District: {profile.member.district}</Badge> : null}
              {profile.member.term_start_year != null ? (
                <Badge variant="soft">
                  Term: {profile.member.term_start_year}–{profile.member.term_end_year ?? 'present'}
                </Badge>
              ) : null}
              <Badge variant="soft">Bioguide: {profile.member.bioguide_id}</Badge>
            </Flex>
          </Flex>
        </Flex>
      </Card>

      <Card size="3">
        <Heading size="4" mb="2">Activity Breakdown</Heading>
        <Flex gap="2" wrap="wrap">
          {Object.entries(activityByType).map(([activityType, count]) => (
            <Badge key={activityType} variant="soft">{activityType}: {count}</Badge>
          ))}
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
