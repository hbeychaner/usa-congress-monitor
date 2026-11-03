import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/shared/queryState.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { billQuery, memberQuery, searchQuery, SEARCH_TYPES } = await import(
    `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
);

for (const [name, codec, query] of [
    ['bill', billQuery, 'query=Health+%26+care&congress=119&chamber=House&bill_type=hr&subject=Children%27s+health&has_votes=true&page=3'],
    ['member', memberQuery, 'query=O%27Brien&state=South+Dakota&chamber=Senate&party=Independent&page=2'],
    ['search', searchQuery, 'q=Health+%26+%E2%9C%93&types=member,bill&limit=28'],
]) {
    test(`${name} defaults serialize without noisy default parameters`, () => {
        const parsed = codec.read(new URLSearchParams());
        assert.equal(parsed.error, null);
        assert.equal(codec.write(parsed.value).toString(), '');
    });

    test(`${name} applied state survives encoding, copied links, and refresh`, () => {
        const initial = codec.read(new URLSearchParams(query));
        assert.equal(initial.error, null);
        const encoded = codec.write(initial.value);
        const restored = codec.read(new URLSearchParams(encoded.toString()));
        assert.equal(restored.error, null);
        assert.deepEqual(restored.value, initial.value);
        assert.equal(codec.write(restored.value).toString(), encoded.toString());
    });
}

for (const [name, codec] of [['bill', billQuery], ['member', memberQuery]]) {
    for (const raw of ['0', '-1', '1.5', '1e2', '', '9007199254740992', '1&page=2']) {
        test(`${name} malformed page '${raw}' is explicit, never a silently valid page`, () => {
            const parsed = codec.read(new URLSearchParams(`page=${raw}`));
            assert.match(parsed.error?.message ?? '', /Invalid URL parameter 'page'/);
            assert.equal(parsed.value.page, 1);
        });
    }

    test(`${name} paging preserves every applied filter and a new submission resets only the page`, () => {
        const parsed = codec.read(new URLSearchParams(name === 'bill'
            ? 'subject=Health&query=care&congress=119&chamber=House&bill_type=hr&has_votes=true&page=2'
            : 'query=Smith&state=CA&chamber=House&party=Independent&page=2'));
        const next = codec.read(codec.write({ ...parsed.value, page: 3 }));
        assert.deepEqual(next.value, { ...parsed.value, page: 3 });
        const reset = codec.write({ ...parsed.value, page: 1 });
        assert.equal(reset.has('page'), false);
        assert.deepEqual(codec.read(reset).value, { ...parsed.value, page: 1 });
    });
}

test('existing subject-only bill links remain valid', () => {
    const parsed = billQuery.read(new URLSearchParams('subject=Health+%26+care'));
    assert.equal(parsed.error, null);
    assert.equal(parsed.value.subject, 'Health & care');
    assert.equal(parsed.value.page, 1);
});

for (const raw of ['true', '1', 'yes', 'on', 'TRUE']) {
    test(`bill vote flag '${raw}' stays true and canonicalizes`, () => {
        const parsed = billQuery.read(new URLSearchParams(`has_votes=${raw}`));
        assert.equal(parsed.error, null);
        assert.equal(parsed.value.hasVotes, true);
        assert.equal(billQuery.write(parsed.value).get('has_votes'), 'true');
    });
}

for (const raw of ['false', '0', 'no', 'off', 'FALSE']) {
    test(`bill vote flag '${raw}' stays false and omits the default`, () => {
        const parsed = billQuery.read(new URLSearchParams(`has_votes=${raw}`));
        assert.equal(parsed.error, null);
        assert.equal(parsed.value.hasVotes, false);
        assert.equal(billQuery.write(parsed.value).has('has_votes'), false);
    });
}

for (const query of ['has_votes=invalid', 'has_votes=', 'chamber=unknown', 'bill_type=unknown', 'subject=one&subject=two']) {
    test(`invalid bill URL '${query}' carries an actionable error`, () => {
        assert.match(billQuery.read(new URLSearchParams(query)).error?.message ?? '', /Invalid URL parameter/);
    });
}

test('type/chamber casing canonicalizes without losing the selection', () => {
    const parsed = billQuery.read(new URLSearchParams('chamber=house&bill_type=HR'));
    assert.equal(parsed.error, null);
    assert.equal(parsed.value.chamber, 'House');
    assert.equal(parsed.value.billType, 'hr');
});

test('search types are closed, deduplicated and serialized in canonical order', () => {
    const parsed = searchQuery.read(new URLSearchParams('q=health&types=BILL,member,member'));
    assert.equal(parsed.error, null);
    assert.deepEqual(parsed.value.types, ['member', 'bill']);
    assert.equal(searchQuery.write(parsed.value).get('types'), 'member,bill');
    assert.match(searchQuery.read(new URLSearchParams('q=health&types=member,unknown')).error?.message ?? '', /'types'/);
});

test('an empty search selection means all types, not an ambiguous empty result', () => {
    const parsed = searchQuery.read(new URLSearchParams('types='));
    assert.equal(parsed.error, null);
    assert.deepEqual(parsed.value.types, SEARCH_TYPES);
    assert.equal(searchQuery.write({ ...parsed.value, types: [] }).has('types'), false);
});

for (const limit of ['1', '28', '100']) {
    test(`valid per-type search limit '${limit}' round-trips`, () => {
        const parsed = searchQuery.read(new URLSearchParams(`limit=${limit}`));
        assert.equal(parsed.error, null);
        assert.equal(searchQuery.read(searchQuery.write(parsed.value)).value.limit, Number(limit));
    });
}

for (const limit of ['0', '101', '-1', 'invalid', '28.5', '']) {
    test(`invalid per-type search limit '${limit}' does not look valid`, () => {
        assert.match(searchQuery.read(new URLSearchParams(`limit=${limit}`)).error?.message ?? '', /'limit'/);
    });
}
