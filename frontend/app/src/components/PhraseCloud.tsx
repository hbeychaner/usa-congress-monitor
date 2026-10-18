import { Flex } from '@radix-ui/themes';

import type { TermUse } from '../api/parties';

const MAX_SIZE_REM = 1.8;
const MIN_SIZE_REM = 0.85;
const MAX_OPACITY = 1;
const MIN_OPACITY = 0.6;

type PhraseCloudProps = {
  terms: TermUse[];
  color: string;
  selected: string | null;
  onSelect: (term: TermUse) => void;
};

// Terms arrive ranked by distinctiveness, so rank alone drives size and weight.
export function PhraseCloud({ terms, color, selected, onSelect }: PhraseCloudProps) {
  const last = Math.max(terms.length - 1, 1);
  return (
    <Flex wrap="wrap" align="baseline" justify="center" gap="2" style={{ lineHeight: 1.2 }}>
      {terms.map((use, rank) => {
        const weight = 1 - rank / last;
        return (
          <button
            key={use.term}
            type="button"
            title={`${use.bills} bills from ${use.sponsors} sponsors`}
            onClick={() => onSelect(use)}
            style={{
              all: 'unset',
              cursor: 'pointer',
              color,
              fontSize: `${MIN_SIZE_REM + weight * (MAX_SIZE_REM - MIN_SIZE_REM)}rem`,
              fontWeight: weight > 0.5 ? 700 : 500,
              opacity: MIN_OPACITY + weight * (MAX_OPACITY - MIN_OPACITY),
              padding: '0 4px',
              textDecoration: selected === use.term ? 'underline' : 'none',
            }}
          >
            {use.term}
          </button>
        );
      })}
    </Flex>
  );
}
