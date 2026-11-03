import type * as Contracts from '../shared/contracts/api';

export type LabelProvenance = Pick<Contracts.TopicSummary, 'label_source' | 'fallback_reason'>;

export const labelSources: Record<Contracts.LabelSource, string> = {
  unknown: 'Label origin unknown',
  llm: 'LLM-generated label',
  keywords: 'Keyword-derived label',
  largest_topic: 'Largest-topic label',
  override: 'Override label',
  deterministic: 'Deterministic label',
};

export const labelFallbackReasons: Record<Contracts.LabelFallbackReason, string> = {
  disabled: 'LLM labeling was disabled',
  unavailable: 'LLM was unavailable',
  request_failed: 'LLM request failed',
  invalid_response: 'LLM response was unusable',
  name_collision: 'Generated name already in use',
};

export function labelOriginDescription(origin: LabelProvenance): string {
  const reason = origin.fallback_reason;
  return labelSources[origin.label_source] + (reason ? `: ${labelFallbackReasons[reason]}` : '');
}
