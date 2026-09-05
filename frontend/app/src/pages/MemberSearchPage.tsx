import { Badge, Button, Card, Flex, Heading, Select, Table, Text, TextField } from '@radix-ui/themes';
import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchMembers, type MemberFilters, type MemberSummary } from '../api/members';

const PAGE_SIZE = 50;

export function MemberSearchPage() {
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<MemberFilters>({});
  const [draft, setDraft] = useState<MemberFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchMembers(page, PAGE_SIZE, filters).then((response) => {
      if (cancelled) return;
      setMembers(response.members);
      setTotal(response.total);
      setError(null);
    }).catch((err: Error) => {
      if (!cancelled) setError(err.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [page, filters]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  }

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="end" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">People directory</Text>
          <Heading size="7">Members</Heading>
          <Text color="gray">Find current and historical members by identity, state, chamber, or party.</Text>
        </Flex>
        <Badge size="2" variant="soft">{loading ? 'Loading' : `${total.toLocaleString()} records`}</Badge>
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
                <Select.Trigger placeholder="All parties" />
                <Select.Content>
                  <Select.Item value="all">All parties</Select.Item>
                  <Select.Item value="Democratic">Democratic</Select.Item>
                  <Select.Item value="Republican">Republican</Select.Item>
                  <Select.Item value="Independent">Independent</Select.Item>
                </Select.Content>
              </Select.Root>
            </label>
            <Button type="submit">Apply filters</Button>
          </Flex>
        </form>
      </Card>

      {error ? <Card size="3"><Text as="p">Unable to load members: {error}</Text></Card> : null}
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

      <Flex justify="center" align="center" gap="3" aria-label="Member pages">
        <Button variant="soft" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</Button>
        <Text>Page {page} of {pageCount}</Text>
        <Button disabled={page >= pageCount || loading} onClick={() => setPage(page + 1)}>Next</Button>
      </Flex>
    </Flex>
  );
}
