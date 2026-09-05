import { Badge, Button, Card, Flex, Heading, Select, Table, Text, TextField } from '@radix-ui/themes';
import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchRecentBills, type BillFilters, type BillSummary } from '../api/bills';

const PAGE_SIZE = 50;
const BILL_TYPES = ['hr', 's', 'hres', 'sres', 'hjres', 'sjres', 'hconres', 'sconres'];

function label(bill: BillSummary): string {
  return [bill.bill_type?.toUpperCase(), bill.number].filter(Boolean).join(' ');
}

export function BillsPage() {
  const [bills, setBills] = useState<BillSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<BillFilters>({});
  const [draft, setDraft] = useState<BillFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchRecentBills(PAGE_SIZE, page, filters)
      .then((response) => {
        if (!cancelled) {
          setBills(response.bills);
          setTotal(response.total);
          setError(null);
        }
      })
      .catch((err: Error) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, filters]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  };

  return (
    <Flex direction="column" gap="5">
      <Flex justify="between" align="end" wrap="wrap" gap="3">
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Legislation index</Text>
          <Heading size="7">Bills</Heading>
          <Text color="gray">Browse {total.toLocaleString()} indexed bills with server-side search and filters.</Text>
        </Flex>
        <Badge size="2" variant="soft">
          {loading ? 'Loading' : `${((page - 1) * PAGE_SIZE + (bills.length ? 1 : 0)).toLocaleString()}–${Math.min(page * PAGE_SIZE, total).toLocaleString()}`} of {total.toLocaleString()}
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
                  {BILL_TYPES.filter(Boolean).filter((type, index, list) => list.indexOf(type) === index).map((type) => (
                    <Select.Item key={type} value={type}>{type.toUpperCase()}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </label>
            <Button type="submit">Apply filters</Button>
          </Flex>
        </form>
      </Card>

      {error ? <Card size="3"><Text as="p">Unable to load bills: {error}</Text></Card> : null}
      {!loading && !error && bills.length === 0 ? <Card size="3"><Text as="p">No bills match these filters.</Text></Card> : null}

      {bills.length > 0 ? (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Bill</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Title</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Congress</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Chamber</Table.ColumnHeaderCell>
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
                <Table.Cell>{bill.updated_at ? new Date(bill.updated_at).toLocaleDateString() : '—'}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      ) : null}

      <Flex justify="center" align="center" gap="3" aria-label="Bill pages">
        <Button variant="soft" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</Button>
        <Text>Page {page} of {pageCount}</Text>
        <Button disabled={page >= pageCount || loading} onClick={() => setPage(page + 1)}>Next</Button>
      </Flex>
    </Flex>
  );
}
