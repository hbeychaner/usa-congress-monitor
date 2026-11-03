import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { createClient } from '@hey-api/openapi-ts';

const { values } = parseArgs({ options: { check: { type: 'boolean' } } });
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const target = resolve(root, 'frontend/app/src/shared/contracts/api.ts');
const schema = execFileSync(
    'uv', ['run', '--frozen', '--project', root, 'python', '-m', 'scripts.export_openapi'],
    { cwd: root, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 },
);
const directory = mkdtempSync(join(tmpdir(), 'congress-contract-types-'));
try {
    await createClient({
        input: JSON.parse(schema),
        output: { path: directory, entryFile: false },
        plugins: [{ name: '@hey-api/typescript', definitions: { case: 'preserve' }, enums: false, comments: false }],
        logs: { level: 'error', file: false },
    });
    const output = readFileSync(join(directory, 'types.gen.ts'), 'utf8');

    if (values.check) {
        if (!existsSync(target) || readFileSync(target, 'utf8') !== output) {
            console.error('API contracts are stale. Run npm run contracts:generate in frontend/app.');
            process.exitCode = 1;
        }
    } else {
        writeFileSync(target, output);
    }
} finally {
    rmSync(directory, { recursive: true, force: true });
}
