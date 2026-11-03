import { Callout, Text } from '@radix-ui/themes';

import { analysisMessages, type AnalysisStatus } from '../api/analysis';
import { ApiError } from '../api/client';

type Props = {
  analysis?: AnalysisStatus | null;
  error?: Error | null;
  loading?: boolean;
  label?: string;
};

export function AnalysisNotice({ analysis, error, loading, label }: Props) {
  if (loading) return <Text as="p" color="gray">Loading analysis...</Text>;
  const state = error
    ? (error instanceof ApiError ? error.analysisState : undefined) ?? 'unavailable'
    : analysis?.state;
  const message = state ? analysisMessages[state] : null;
  if (!message) return null;
  return (
    <Callout.Root color={state === 'unavailable' ? 'red' : 'amber'}>
      <Callout.Text>{label ? `${label}: ` : ''}{message}</Callout.Text>
    </Callout.Root>
  );
}
