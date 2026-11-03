import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', '""');
const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { ApiError, apiGet, apiPost } = await import(
    `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
);

for (const [status, body, message] of [
    [404, '{"detail":"Bill not found"}', 'Bill not found'],
    [409, '{"detail":"Another build is active"}', 'Another build is active'],
    [422, '{"detail":[{"msg":"Limit must be positive"},{"msg":"Invalid chamber"}]}',
        'Limit must be positive; Invalid chamber'],
    [503, '{"detail":"Search service unavailable; please try again later."}',
        'Search service unavailable; please try again later.'],
    [500, '<html>private gateway diagnostics</html>', 'Request failed: 500'],
    [502, '{"detail":', 'Request failed: 502'],
]) {
    test(`GET and POST preserve safe HTTP ${status} detail and status`, async (context) => {
        context.mock.method(globalThis, 'fetch', async () => new Response(body, { status }));
        for (const request of [apiGet, apiPost]) {
            await assert.rejects(request('/fixture'), error =>
                error instanceof ApiError && error.status === status && error.message === message);
        }
    });
}

test('successful JSON and network failures are not converted into empty results', async (context) => {
    const calls = [];
    context.mock.method(globalThis, 'fetch', async (path, options) => {
        calls.push({ path, method: options.method });
        return Response.json({ results: [] });
    });

    assert.deepEqual(await apiGet('/search'), { results: [] });
    assert.deepEqual(await apiPost('/start'), { results: [] });
    assert.deepEqual(calls, [{ path: '/search', method: 'GET' }, { path: '/start', method: 'POST' }]);
    context.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network unavailable'); });
    await assert.rejects(apiGet('/search'), /Network unavailable/);
});

for (const state of ['not_built', 'unavailable']) {
    test(`HTTP 503 preserves ${state} without inventing an empty result`, async (context) => {
        context.mock.method(globalThis, 'fetch', async () =>
            Response.json({ detail: 'Safe detail', analysis_state: state }, { status: 503 }));
        await assert.rejects(apiGet('/analysis'), error =>
            error instanceof ApiError && error.status === 503 && error.analysisState === state);
    });
}

test('unknown error metadata does not become a trusted analysis state', async (context) => {
    context.mock.method(globalThis, 'fetch', async () =>
        Response.json({ detail: 'Safe detail', analysis_state: 'available' }, { status: 503 }));
    await assert.rejects(apiGet('/analysis'), error =>
        error instanceof ApiError && error.analysisState === undefined);
});
