import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/shared/billText.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;
const { billTextFormatLabel, billTextHeading, isEnactedLawText } = await import(
    `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
);

test('partial source facsimiles are explicit without changing ordinary formats', () => {
    assert.equal(billTextFormatLabel({type:'PDF',coverage:'partial'}), 'PDF (partial facsimile)');
    assert.equal(billTextFormatLabel({type:'PDF'}), 'PDF');
    assert.equal(billTextFormatLabel({}), 'Link');
});

test('enacted law headings distinguish public and private law from bill drafts', () => {
    assert.equal(billTextHeading('public-law-95-367'), 'Enacted public law text (95-367)');
    assert.equal(billTextHeading('private-law-94-48'), 'Enacted private law text (94-48)');
    assert.equal(isEnactedLawText('public-law-95-367'), true);
    assert.equal(isEnactedLawText('private-law-94-48'), true);
});

test('ordinary and absent versions preserve legacy presentation', () => {
    for (const version of [null, undefined, '']) {
        assert.equal(billTextHeading(version), 'Full text');
        assert.equal(isEnactedLawText(version), false);
    }
    assert.equal(billTextHeading('ih'), 'Full text (version IH)');
    assert.equal(isEnactedLawText('ih'), false);
    assert.equal(isEnactedLawText('public-law-0-1'), false);
    assert.equal(isEnactedLawText('public-law-95-367-extra'), false);
});
