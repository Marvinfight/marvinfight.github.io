import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputFile = path.join(projectRoot, 'dist', 'index.html');

test('build output includes assets under the /zysd/ base path', () => {
  assert.ok(
    fs.existsSync(outputFile),
    `Expected build output at ${outputFile}. Run \"npm run build\" before running this test.`,
  );

  const html = fs.readFileSync(outputFile, 'utf8');
  assert.match(html, /\/zysd\/assets\//);
});
