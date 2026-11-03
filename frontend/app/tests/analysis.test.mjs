import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/api/analysis.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { analysisMessages } = await import(
    `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
);

test('analysis notices distinguish unbuilt, empty, stale, unknown, and unavailable', () => {
    assert.equal(analysisMessages.available, null);
    assert.match(analysisMessages.not_built, /not been built and published/);
    assert.match(analysisMessages.empty, /available.*no results match/);
    assert.doesNotMatch(analysisMessages.empty, /train|not.*built/);
    assert.match(analysisMessages.stale, /different topic model.*previous results/);
    assert.match(analysisMessages.unknown, /lineage is unknown/);
    assert.match(analysisMessages.unavailable, /unavailable/);
    assert.equal(new Set(Object.values(analysisMessages)).size, 6);
});
