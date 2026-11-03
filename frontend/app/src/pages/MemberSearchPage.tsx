import { Badge, Button, Card, Flex, Heading, Select, Table, Text, TextField } from '@radix-ui/themes';
import { useCallback, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchMembers } from '../api/members';
import { PageControls } from '../components/PageControls';
import { useRead } from '../hooks/useRead';
import { useQueryForm } from '../hooks/useQueryForm';
import { memberQuery } from '../shared/queryState';

const PAGE_SIZE = 50;

export function MemberSearchPage() {
  const { applied, draft, setDraft, apply, error: urlError, requestKey } = useQueryForm(memberQuery);
  const request = useCallback(() => fetchMembers(applied.page, PAGE_SIZE, applied), [applied, requestKey]);
  const { data, error: readError, loading } = useRead(urlError ? null : request);
  const error = urlError ?? readError;
  const page = applied.page;
  const members = data?.members ?? [];
  const total = data?.total ?? 0;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    apply({ ...draft, page: 1 });
  }

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="end" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">People directory</Text>
          <Heading size="7">Members</Heading>
          <Text color="gray">Find current and historical members by identity, state, chamber, or party.</Text>
        </Flex>
        <Badge size="2" variant="soft">{loading ? 'Loading' : data ? `${total.toLocaleString()} records` : 'Unavailable'}</Badge>
      </Flex>

      <Card size="3" asChild>
        <form onSubmit={onSubmit}>
          <Flex wrap="wrap" gap="3" align="end">
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Search</Text>
              <TextField.Root
                value={draft.query ?? ''}
                onChange={(event) => setDraft({ ...draft, query: event.target.value })}
                placeholder="Name, state, or Bioguide ID"
              />
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">State</Text>
              <TextField.Root
                value={draft.state ?? ''}
                onChange={(event) => setDraft({ ...draft, state: event.target.value })}
                placeholder="South Dakota"
              />
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Chamber</Text>
              <Select.Root value={draft.chamber ?? 'all'} onValueChange={(value) => setDraft({ ...draft, chamber: value === 'all' ? undefined : value })}>
                <Select.Trigger placeholder="All chambers" />
                <Select.Content>
                  <Select.Item value="all">All chambers</Select.Item>
                  <Select.Item value="House">House</Select.Item>
                  <Select.Item value="Senate">Senate</Select.Item>
                </Select.Content>
              </Select.Root>
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Party</Text>
              <Select.Root value={draft.party ?? 'all'} onValueChange={(value) => setDraft({ ...draft, party: value === 'all' ? undefined : value })}>
                <Select.Trigger>{draft.party ?? 'All parties'}</Select.Trigger>
                <Select.Content>
                  <Select.Item value="all">All parties</Select.Item>
                  {[...new Set(['Democratic', 'Republican', 'Independent', ...(applied.party ? [applied.party] : [])])].map(party => (
                    <Select.Item key={party} value={party}>{party}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </label>
            <Button type="submit">Apply filters</Button>
          </Flex>
        </form>
      </Card>

      {error ? <Card size="3" role="alert"><Text as="p">Unable to load members: {error.message}</Text></Card> : null}
      {!loading && !error && members.length === 0 ? <Card size="3"><Text as="p">No members match these filters.</Text></Card> : null}

      {members.length > 0 ? (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Member</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Party</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>State</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Chamber</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>District</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Term</Table.ColumnHeaderCell>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {members.map((member) => (
              <Table.Row key={member.bioguide_id}>
                <Table.RowHeaderCell>
                  <Link to={`/members/${encodeURIComponent(member.bioguide_id)}`}>{member.display_name}</Link>
                  <Text as="div" size="1" color="gray">{member.bioguide_id}</Text>
                </Table.RowHeaderCell>
                <Table.Cell>{member.party}</Table.Cell>
                <Table.Cell>{member.state}</Table.Cell>
                <Table.Cell>{member.chamber ?? 'Not recorded'}</Table.Cell>
                <Table.Cell>{member.district ?? 'At-large / not recorded'}</Table.Cell>
                <Table.Cell>{member.term_start_year ?? 'Not recorded'}–{member.term_end_year ?? 'present'}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      ) : null}

      {!urlError ? <PageControls page={page} bounds={data} loading={loading} onChange={page => apply({ ...applied, page })} /> : null}
    </Flex>
  );
}
