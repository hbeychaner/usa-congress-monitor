import { Text } from '@radix-ui/themes';
import { labelOriginDescription } from '../api/labels';
import type { LabelProvenance } from '../api/labels';

export function LabelOrigin({ origin }: { origin: LabelProvenance }) {
  return <Text as="p" size="1" color="gray" title="Origin recorded when this label was created.">{labelOriginDescription(origin)}</Text>;
}
