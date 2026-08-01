import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputFile = path.join(projectRoot, 'dist', 'index.html');

function readBuiltOutput() {
  const html = fs.readFileSync(outputFile, 'utf8');
  const assetReferences = [
    ...html.matchAll(/(?:src|href)="(\/zysd\/assets\/[^"?]+)(?:\?[^\"]*)?"/g),
  ].map((match) => match[1]);
  const assets = assetReferences.map((assetReference) =>
    fs.readFileSync(path.join(projectRoot, 'dist', assetReference.slice('/zysd/'.length)), 'utf8'),
  );

  return [html, ...assets].join('\n');
}

test('build output includes assets under the /zysd/ base path', () => {
  assert.ok(
    fs.existsSync(outputFile),
    `Expected build output at ${outputFile}. Run "pnpm.cmd run build" before running this test.`,
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

test('build output includes the calculator title and result labels', () => {
  assert.ok(
    fs.existsSync(outputFile),
    `Expected build output at ${outputFile}. Run "pnpm.cmd run build" before running this test.`,
  );

  const output = readBuiltOutput();
  const expectedLabels = [
    '江苏电力曲线计算器',
    '2026 曲线优势/均价',
    '2027 曲线优势/均价',
  ];

  for (const label of expectedLabels) {
    assert.ok(output.includes(label), `Expected build output to include "${label}".`);
  }
});
