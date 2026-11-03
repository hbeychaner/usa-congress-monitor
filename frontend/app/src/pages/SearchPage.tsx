import { Button, Card, Flex, Heading, Select, Text, TextField } from '@radix-ui/themes';
import { useCallback, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { fetchSearch, type SearchResponse } from '../api/search';
import { useRead } from '../hooks/useRead';
import { useQueryForm } from '../hooks/useQueryForm';
import { searchQuery, SEARCH_TYPES, type SearchKind } from '../shared/queryState';

function resultHref(resultType: string, id: string): string | null {
    if (resultType === 'member') {
        return `/members/${encodeURIComponent(id)}`;
    }
    if (resultType === 'state') {
        return `/states/${encodeURIComponent(id)}`;
    }
    if (resultType === 'bill') {
        return `/bills/${encodeURIComponent(id)}`;
    }
    return null;
}

export function SearchPage() {
    const { applied, draft, setDraft, apply, error: urlError, requestKey } = useQueryForm(searchQuery);
    const { query, types: selectedTypes, limit } = draft;
    const request = useCallback(() => fetchSearch(applied), [applied, requestKey]);
    const { data: result, error: readError, loading } = useRead(!urlError && applied.query ? request : null);
    const error = urlError ?? readError;

    const groupedResults = (result?.results ?? []).reduce<Record<string, SearchResponse['results']>>(
        (acc, item) => {
            const group = item.result_type || 'other';
            acc[group] = [...(acc[group] ?? []), item];
            return acc;
        },
        {}
    );

    function toggleType(type: SearchKind) {
        setDraft(previous => ({ ...previous, types: previous.types.includes(type)
            ? previous.types.filter(item => item !== type) : [...previous.types, type] }));
    }

    function onSubmit(event: FormEvent) {
        event.preventDefault();
        apply(draft);
    }

    return (
        <Flex direction="column" gap="5">
            <Heading size="7">Search</Heading>

            <Card size="3" asChild>
                <form onSubmit={onSubmit}>
                    <Flex gap="3" wrap="wrap">
                        <TextField.Root
                            style={{ flex: '1 1 15rem', minWidth: 0 }}
                            value={query}
                            onChange={(event) => setDraft({ ...draft, query: event.target.value })}
                            aria-label="Search query"
                            placeholder="Search members, states, bills"
                        />
                        <Button type="submit" disabled={!query || loading}>
                            {loading ? 'Searching...' : 'Search'}
                        </Button>
                    </Flex>
                </form>
            </Card>

            <Card size="3">
                <Heading size="4" mb="2">Filters</Heading>
                <Flex gap="2" wrap="wrap" mb="3">
                    {SEARCH_TYPES.map((type) => (
                        <Button
                            key={type}
                            type="button"
                            variant={selectedTypes.includes(type) ? 'solid' : 'soft'}
                            aria-pressed={selectedTypes.includes(type)}
                            onClick={() => toggleType(type)}
                        >
                            {type}
                        </Button>
                    ))}
                </Flex>
                <label>
                    <Text as="div" size="2" mb="1" weight="medium">Results per type</Text>
                    <Select.Root value={String(limit)} onValueChange={(value) => setDraft({ ...draft, limit: Number(value) })}>
                        <Select.Trigger />
                        <Select.Content>
                            {[...new Set([10, 20, 50, 100, limit])].sort((a, b) => a - b).map((option) => (
                                <Select.Item key={option} value={String(option)}>{option}</Select.Item>
                            ))}
                        </Select.Content>
                    </Select.Root>
                </label>
            </Card>

            {error ? <Card size="3" role="alert"><Text as="p">Search failed: {error.message}</Text></Card> : null}
            {result ? (
                <>
                    <Card size="3">
                        <Heading size="4" mb="1">Search Summary</Heading>
                        <Text as="p">
                            Query: <Text weight="bold">{result.query}</Text> · Types: {result.types.join(', ')} · Results per type: {result.limit}. Groups are not globally ranked.
                        </Text>
                    </Card>

                    {result.results.length === 0 ? (
                        <Card size="3">
                            <Heading size="4" mb="1">No Results</Heading>
                            <Text as="p">
                                No matching records were found for this query.
                            </Text>
                            <Text as="p">
                                Try exploring <Link to="/states">states map</Link> or the{' '}
                                <Link to="/members/H001092">member profile</Link>.
                            </Text>
                        </Card>
                    ) : (
                        Object.entries(groupedResults).map(([group, items]) => (
                            <Card size="3" key={group}>
                                <Heading size="4" mb="2">{group.toUpperCase()}</Heading>
                                <Flex direction="column" gap="2">
                                    {items.map((item) => (
                                        <Text as="p" key={item.id}>
                                            {resultHref(item.result_type, item.id) ? (
                                                <Link to={resultHref(item.result_type, item.id) ?? '#'}>
                                                    <Text weight="bold">{item.title}</Text>
                                                </Link>
                                            ) : (
                                                <Text weight="bold">{item.title}</Text>
                                            )}
                                            {item.subtitle ? <Text color="gray"> · {item.subtitle}</Text> : null}
                                        </Text>
                                    ))}
                                </Flex>
                            </Card>
                        ))
                    )}
                </>
            ) : null}
        </Flex>
    );
}
