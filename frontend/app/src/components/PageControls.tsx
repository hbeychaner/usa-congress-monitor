import { Button, Flex, Text } from '@radix-ui/themes';
import type { BillsResponse } from '../api/bills';

type PageBounds = Pick<BillsResponse, 'max_page' | 'max_result_window' | 'window_limited'>;

export function PageControls({ page, bounds, loading, onChange }: {
  page: number;
  bounds: PageBounds | null;
  loading: boolean;
  onChange: (page: number) => void;
}) {
  return (
    <Flex direction="column" gap="2" align="center">
      {bounds?.window_limited ? (
        <Text size="2" color="gray">
          Browsing covers the first {bounds.max_result_window.toLocaleString()} matches, not all matches. Refine the filters to find others.
        </Text>
      ) : null}
      <Flex gap="3" align="center" aria-label="Result pages">
        <Button variant="soft" disabled={loading || page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
        <Text>{loading ? 'Loading page...' : bounds ? `Page ${page} of ${bounds.max_page}` : `Page ${page}`}</Text>
        <Button disabled={loading || !bounds || page >= bounds.max_page} onClick={() => onChange(page + 1)}>Next</Button>
      </Flex>
    </Flex>
  );
}
