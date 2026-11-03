import { Badge, Button, Card, Checkbox, Flex, Heading, Select, Table, Text, TextField } from '@radix-ui/themes';
import { useCallback, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchRecentBills, type BillSummary } from '../api/bills';
import { PageControls } from '../components/PageControls';
import { useRead } from '../hooks/useRead';
import { useQueryForm } from '../hooks/useQueryForm';
import { billQuery, BILL_TYPES } from '../shared/queryState';

const PAGE_SIZE = 50;

function label(bill: BillSummary): string {
  return [bill.bill_type?.toUpperCase(), bill.number].filter(Boolean).join(' ');
}

export function BillsPage() {
  const { applied, draft, setDraft, apply, error: urlError, requestKey } = useQueryForm(billQuery);
  const request = useCallback(() => fetchRecentBills(PAGE_SIZE, applied.page, applied), [applied, requestKey]);
  const { data, error: readError, loading } = useRead(urlError ? null : request);
  const error = urlError ?? readError;
  const page = applied.page;
  const bills = data?.bills ?? [];
  const total = data?.total ?? 0;

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    apply({ ...draft, page: 1 });
  };

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="end" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Legislation index</Text>
          <Heading size="7">Bills</Heading>
          <Text color="gray">Browse {data ? `${total.toLocaleString()} ` : ''}indexed bills with server-side search and filters.</Text>
        </Flex>
        <Badge size="2" variant="soft">
          {loading ? 'Loading' : data ? `${((page - 1) * PAGE_SIZE + (bills.length ? 1 : 0)).toLocaleString()}–${Math.min(page * PAGE_SIZE, total).toLocaleString()} of ${total.toLocaleString()}` : 'Unavailable'}
        </Badge>
      </Flex>

      <Card size="3" asChild>
        <form onSubmit={applyFilters}>
          <Flex wrap="wrap" gap="3" align="end">
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Search bills</Text>
              <TextField.Root
                value={draft.query ?? ''}
                onChange={(event) => setDraft({ ...draft, query: event.target.value })}
                placeholder="Title, sponsor, policy area, or bill ID"
              />
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Congress</Text>
              <TextField.Root
                inputMode="numeric"
                value={draft.congress ?? ''}
                onChange={(event) => setDraft({ ...draft, congress: event.target.value })}
                placeholder="119"
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
              <Text as="div" size="2" mb="1" weight="medium">Type</Text>
              <Select.Root value={draft.billType ?? 'all'} onValueChange={(value) => setDraft({ ...draft, billType: value === 'all' ? undefined : value })}>
                <Select.Trigger placeholder="All types" />
                <Select.Content>
                  <Select.Item value="all">All types</Select.Item>
                  {BILL_TYPES.map((type) => (
                    <Select.Item key={type} value={type}>{type.toUpperCase()}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Subject</Text>
              <TextField.Root
                value={draft.subject ?? ''}
                onChange={(event) => setDraft({ ...draft, subject: event.target.value || undefined })}
                placeholder="e.g. Health"
              />
            </label>
            <label>
              <Flex align="center" gap="2" style={{ height: 'var(--space-6)' }}>
                <Checkbox
                  checked={draft.hasVotes ?? false}
                  onCheckedChange={(checked) => setDraft({ ...draft, hasVotes: checked === true })}
                />
                <Text size="2" weight="medium">Has votes</Text>
              </Flex>
            </label>
            <Button type="submit">Apply filters</Button>
          </Flex>
        </form>
      </Card>

      {error ? <Card size="3" role="alert"><Text as="p">Unable to load bills: {error.message}</Text></Card> : null}
      {!loading && !error && bills.length === 0 ? <Card size="3"><Text as="p">No bills match these filters.</Text></Card> : null}

      {bills.length > 0 ? (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Bill</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Title</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Congress</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Chamber</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Votes</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Updated</Table.ColumnHeaderCell>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {bills.map((bill) => (
              <Table.Row key={bill.bill_id}>
                <Table.RowHeaderCell>
                  <Link to={`/bills/${encodeURIComponent(bill.bill_id)}`}>{label(bill) || bill.bill_id}</Link>
                </Table.RowHeaderCell>
                <Table.Cell>{bill.title}</Table.Cell>
                <Table.Cell>{bill.congress ?? '—'}</Table.Cell>
                <Table.Cell>{bill.chamber ?? '—'}</Table.Cell>
                <Table.Cell>{bill.vote_count ? <Badge color="blue">{bill.vote_count}</Badge> : '—'}</Table.Cell>
                <Table.Cell>{bill.updated_at ? new Date(bill.updated_at).toLocaleDateString() : '—'}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      ) : null}

      {!urlError ? <PageControls page={page} bounds={data} loading={loading} onChange={page => apply({ ...applied, page })} /> : null}
    </Flex>
  );
}
