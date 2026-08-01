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
  const assetReferences = [
    ...html.matchAll(/(?:src|href)="(\/zysd\/assets\/[^"?]+)(?:\?[^\"]*)?"/g),
  ].map((match) => match[1]);

  assert.ok(
    assetReferences.length > 0,
    'Expected built HTML to reference at least one /zysd/assets/ file.',
  );

  for (const assetReference of assetReferences) {
    const assetFile = path.join(
      projectRoot,
      'dist',
      assetReference.slice('/zysd/'.length),
    );
    assert.ok(fs.existsSync(assetFile), `Expected built asset at ${assetFile}.`);
  }
});
