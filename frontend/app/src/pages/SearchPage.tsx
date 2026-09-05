import { Button, Card, Flex, Heading, Select, Text, TextField } from '@radix-ui/themes';
import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';

import { fetchSearch, type SearchResponse } from '../api/search';

const SEARCH_TYPES = ['member', 'state', 'bill'] as const;

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
    const [query, setQuery] = useState('');
    const [selectedTypes, setSelectedTypes] = useState<string[]>([...SEARCH_TYPES]);
    const [limit, setLimit] = useState(20);
    const [result, setResult] = useState<SearchResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const groupedResults = (result?.results ?? []).reduce<Record<string, SearchResponse['results']>>(
        (acc, item) => {
            const group = item.result_type || 'other';
            acc[group] = [...(acc[group] ?? []), item];
            return acc;
        },
        {}
    );

    function toggleType(type: string) {
        setSelectedTypes((previous) => {
            if (previous.includes(type)) {
                return previous.filter((item) => item !== type);
            }
            return [...previous, type];
        });
    }

    async function onSubmit(event: FormEvent) {
        event.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const data = await fetchSearch({
                query,
                types: selectedTypes.length > 0 ? selectedTypes : [...SEARCH_TYPES],
                limit,
            });
            setResult(data);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <Flex direction="column" gap="5">
            <Heading size="7">Search</Heading>

            <Card size="3" asChild>
                <form onSubmit={onSubmit}>
                    <Flex gap="3" wrap="wrap">
                        <TextField.Root
                            style={{ flex: 1, minWidth: '240px' }}
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
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
                            onClick={() => toggleType(type)}
                        >
                            {type}
                        </Button>
                    ))}
                </Flex>
                <label>
                    <Text as="div" size="2" mb="1" weight="medium">Result limit</Text>
                    <Select.Root value={String(limit)} onValueChange={(value) => setLimit(Number(value))}>
                        <Select.Trigger />
                        <Select.Content>
                            {[10, 20, 50].map((option) => (
                                <Select.Item key={option} value={String(option)}>{option}</Select.Item>
                            ))}
                        </Select.Content>
                    </Select.Root>
                </label>
            </Card>

            {error ? <Card size="3"><Text as="p">Search failed: {error}</Text></Card> : null}
            {result ? (
                <>
                    <Card size="3">
                        <Heading size="4" mb="1">Search Summary</Heading>
                        <Text as="p">
                            Query: <Text weight="bold">{result.query}</Text> · Types: {result.types.join(', ')} · Limit: {result.limit}
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
