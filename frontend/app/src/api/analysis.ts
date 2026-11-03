import type * as Contracts from '../shared/contracts/api';

export type AnalysisStatus = Contracts.AnalysisStatus;
export type AnalysisState = Contracts.AnalysisState;

export const analysisMessages: Record<AnalysisState, string | null> = {
  available: null,
  not_built: 'Analysis has not been built and published yet.',
  empty: 'Analysis is available, but no results match this selection.',
  stale: 'Analysis uses a different topic model from the published model; showing the previous results.',
  unknown: 'Analysis lineage is unknown; freshness cannot be verified.',
  unavailable: 'Analysis is unavailable. Please try again later.',
};
