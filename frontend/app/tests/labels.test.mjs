import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/api/labels.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { labelOriginDescription, labelSources, labelFallbackReasons } = await import(
    `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
);

test('label sources distinguish generated, fallback, override and legacy names', () => {
    assert.equal(new Set(Object.values(labelSources)).size, 6);
    for (const [label_source, message] of Object.entries(labelSources)) {
        assert.equal(labelOriginDescription({ label_source, fallback_reason: null }), message);
    }
    assert.match(labelSources.llm, /LLM-generated/);
    assert.match(labelSources.unknown, /unknown/);
    assert.doesNotMatch(labelSources.unknown, /generated/);
});

test('fallback explanations are distinct historical categories, not exception text', () => {
    assert.equal(new Set(Object.values(labelFallbackReasons)).size, 5);
    for (const [fallback_reason, message] of Object.entries(labelFallbackReasons)) {
        assert.equal(labelOriginDescription({
            label_source: 'keywords', fallback_reason,
        }), `Keyword-derived label: ${message}`);
    }
    assert.match(labelFallbackReasons.disabled, /was disabled/);
    assert.match(labelFallbackReasons.unavailable, /was unavailable/);
    assert.notEqual(labelFallbackReasons.request_failed, labelFallbackReasons.invalid_response);
});
