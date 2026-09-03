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
        <section>
            <h1>Search</h1>
            <form className="search-form" onSubmit={onSubmit}>
                <input
                    className="search-input"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search members, states, bills"
                />
                <button className="button" type="submit" disabled={!query || loading}>
                    {loading ? 'Searching...' : 'Search'}
                </button>
            </form>

            <div className="search-filters panel">
                <h2>Filters</h2>
                <div className="chip-row">
                    {SEARCH_TYPES.map((type) => (
                        <button
                            key={type}
                            type="button"
                            className={`chip-button ${selectedTypes.includes(type) ? 'chip-button-active' : ''}`}
                            onClick={() => toggleType(type)}
                        >
                            {type}
                        </button>
                    ))}
                </div>
                <label className="limit-label">
                    Result limit
                    <select
                        className="search-input"
                        value={limit}
                        onChange={(event) => setLimit(Number(event.target.value))}
                    >
                        {[10, 20, 50].map((option) => (
                            <option key={option} value={option}>
                                {option}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            {error ? <p>Search failed: {error}</p> : null}
            {result ? (
                <>
                    <div className="panel">
                        <h2>Search Summary</h2>
                        <p>
                            Query: <strong>{result.query}</strong> · Types: {result.types.join(', ')} · Limit: {result.limit}
                        </p>
                    </div>

                    {result.results.length === 0 ? (
                        <div className="panel">
                            <h2>No Results</h2>
                            <p>
                                No matching records were found for this query.
                            </p>
                            <p>
                                Try exploring <Link to="/states">states map</Link> or the{' '}
                                <Link to="/members/H001092">member profile</Link>.
                            </p>
                        </div>
                    ) : (
                        Object.entries(groupedResults).map(([group, items]) => (
                            <div key={group} className="panel">
                                <h2>{group.toUpperCase()}</h2>
                                <ul>
                                    {items.map((item) => (
                                        <li key={item.id}>
                                            {resultHref(item.result_type, item.id) ? (
                                                <Link to={resultHref(item.result_type, item.id) ?? '#'}>
                                                    <strong>{item.title}</strong>
                                                </Link>
                                            ) : (
                                                <strong>{item.title}</strong>
                                            )}
                                            {item.subtitle ? <span> · {item.subtitle}</span> : null}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))
                    )}
                </>
            ) : null}
        </section>
    );
}
