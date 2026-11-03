import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');

test('the solution exposes browser files to the editor with Node types', () => {
    const host = {
        ...ts.sys,
        onUnRecoverableConfigFileDiagnostic: diagnostic => {
            throw new Error(ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'));
        },
    };
    const solution = ts.getParsedCommandLineOfConfigFile(resolve(app, 'tsconfig.json'), {}, host);
    assert.ok(solution);
    const browserPath = resolve(app, 'tsconfig.browser.json');
    assert.ok(solution.projectReferences.some(reference => reference.path === browserPath));
    const browser = ts.getParsedCommandLineOfConfigFile(browserPath, {}, host);
    assert.ok(browser);
    assert.deepEqual(browser.errors, []);
    assert.ok(browser.fileNames.includes(resolve(app, 'playwright.config.ts')));
    assert.ok(browser.fileNames.includes(resolve(app, 'tests/browser/journeys.spec.ts')));
    assert.ok(browser.options.types.includes('node'));
});

test('the map dependency chain interpolates colors with the patched ESM color package', () => {
    const require = createRequire(import.meta.url);
    const mapsRequire = createRequire(require.resolve('react-simple-maps'));
    const zoomRequire = createRequire(mapsRequire.resolve('d3-zoom'));
    const { interpolateRgb } = zoomRequire('d3-interpolate');
    assert.equal(interpolateRgb('#000000', '#ffffff')(0.5), 'rgb(128, 128, 128)');
    assert.equal(interpolateRgb('#ff0000', '#0000ff')(0.5), 'rgb(128, 0, 128)');
});
