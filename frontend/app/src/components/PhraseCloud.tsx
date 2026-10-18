import { Flex } from '@radix-ui/themes';

const MAX_SIZE_REM = 2;
const MIN_SIZE_REM = 0.8;
const MAX_OPACITY = 1;
const MIN_OPACITY = 0.55;

type PhraseCloudProps = {
  terms: string[];
  color: string;
};

// Terms arrive ranked by distinctiveness, so rank alone drives size and weight.
export function PhraseCloud({ terms, color }: PhraseCloudProps) {
  const last = Math.max(terms.length - 1, 1);
  return (
    <Flex wrap="wrap" align="baseline" justify="center" gap="2" style={{ lineHeight: 1.2 }}>
      {terms.map((term, rank) => {
        const weight = 1 - rank / last;
        return (
          <span
            key={term}
            style={{
              color,
              fontSize: `${MIN_SIZE_REM + weight * (MAX_SIZE_REM - MIN_SIZE_REM)}rem`,
              fontWeight: weight > 0.5 ? 700 : 500,
              opacity: MIN_OPACITY + weight * (MAX_OPACITY - MIN_OPACITY),
              padding: '0 4px',
            }}
          >
            {term}
          </span>
        );
      })}
    </Flex>
  );
}
