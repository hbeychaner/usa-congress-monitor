import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const viteRequire = createRequire(require.resolve('vite/package.json'));
const matcherPath = viteRequire.resolve('picomatch');

test('all Vite glob consumers resolve the same reviewed matcher', () => {
    for (const consumer of ['fdir', 'tinyglobby']) {
        const consumerRequire = createRequire(viteRequire.resolve(consumer));
        assert.equal(consumerRequire.resolve('picomatch'), matcherPath);
    }
});

test('build tooling rejects repeated-extglob near misses without blocking Node', () => {
    const source = `
        const assert = require('node:assert/strict');
        const match = require(${JSON.stringify(matcherPath)});
        for (const pattern of ['+(*)a', '*(*)a', '+(*a)b', '*(*a)b']) {
            assert.equal(match.isMatch('a'.repeat(40) + 'c', pattern), false);
        }
        process.stdout.write('completed');
    `;
    const result = spawnSync(process.execPath, ['-e', source], {
        encoding: 'utf8',
        timeout: 3000,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'completed');
});

test('build globs retain wildcard, extglob, bracket and path matching', () => {
    const matcher = viteRequire('picomatch');
    for (const [pattern, input, expected] of [
        ['**/*.{ts,tsx}', 'src/components/BillCard.tsx', true],
        ['**/*.{ts,tsx}', 'src/components/BillCard.css', false],
        ['**/node_modules/**', 'node_modules/react/index.js', true],
        ['**/node_modules/**', 'src/components/BillCard.tsx', false],
        ['+(a*b)', 'axbayb', true],
        ['+(a*b)', 'axbay', false],
        ['+(*a)', 'aba', true],
        ['+(*a)', 'abb', false],
        ['+(a\\*b)', 'a*ba*b', true],
        ['[[:punct:]]', '\\', true],
        ['[[:punct:]]', 'a', false],
    ]) {
        assert.equal(matcher.isMatch(input, pattern), expected, `${pattern}: ${input}`);
    }
});
