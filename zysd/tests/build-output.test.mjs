import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputFile = path.join(projectRoot, 'dist', 'index.html');
const repositoryRoot = path.resolve(projectRoot, '..');
const pagesWorkflowFile = path.join(repositoryRoot, '.github', 'workflows', 'deploy.yml');
const assemblePagesScript = path.join(projectRoot, 'scripts', 'assemble-pages.mjs');

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

test('build output includes the calculator title and result labels', () => {
  assert.ok(
    fs.existsSync(outputFile),
    `Expected build output at ${outputFile}. Run \"pnpm.cmd run build\" before running this test.`,
  );

  const output = readBuiltOutput();
  const expectedLabels = [
    '江苏电力曲线计算器',
    '2026 曲线优势/均价',
    '2027 曲线优势/均价',
  ];

  for (const label of expectedLabels) {
    assert.ok(output.includes(label), `Expected build output to include \"${label}\".`);
  }
});

test('GitHub Pages workflow builds zysd and deploys the assembled site', () => {
  assert.ok(
    fs.existsSync(pagesWorkflowFile),
    `Expected GitHub Pages workflow at ${pagesWorkflowFile}.`,
  );

  const workflow = fs.readFileSync(pagesWorkflowFile, 'utf8');
  for (const expectedValue of [
    'actions/upload-pages-artifact',
    'actions/deploy-pages',
    'cache-dependency-path: zysd/pnpm-lock.yaml',
    'working-directory: zysd',
    'pnpm install --frozen-lockfile',
    'node zysd/scripts/assemble-pages.mjs',
    'path: _site',
  ]) {
    assert.ok(
      workflow.includes(expectedValue),
      `Expected GitHub Pages workflow to include "${expectedValue}".`,
    );
  }
});

test('Pages artifact preserves legacy HTML and nests the calculator under zysd', () => {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'zysd-pages-'));
  const fixtureDist = path.join(fixtureRoot, 'zysd', 'dist');
  const fixtureOutput = path.join(fixtureRoot, '_site');

  try {
    fs.mkdirSync(path.join(fixtureRoot, 'anfeng'), { recursive: true });
    fs.mkdirSync(path.join(fixtureRoot, '.github', 'workflows'), { recursive: true });
    fs.mkdirSync(path.join(fixtureRoot, 'zysd', 'src'), { recursive: true });
    fs.mkdirSync(path.join(fixtureDist, 'assets'), { recursive: true });
    fs.writeFileSync(path.join(fixtureRoot, 'index.html'), 'legacy root', 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, 'anfeng', 'old.html'), 'legacy page', 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, '.github', 'workflows', 'deploy.yml'), 'private', 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, 'zysd', 'src', 'App.tsx'), 'source', 'utf8');
    fs.writeFileSync(path.join(fixtureDist, 'index.html'), 'calculator', 'utf8');
    fs.writeFileSync(path.join(fixtureDist, 'assets', 'app.js'), 'asset', 'utf8');

    const result = spawnSync(
      process.execPath,
      [assemblePagesScript, fixtureRoot, fixtureDist, fixtureOutput],
      { encoding: 'utf8' },
    );

    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(fs.readFileSync(path.join(fixtureOutput, 'index.html'), 'utf8'), 'legacy root');
    assert.equal(fs.readFileSync(path.join(fixtureOutput, 'anfeng', 'old.html'), 'utf8'), 'legacy page');
    assert.equal(fs.readFileSync(path.join(fixtureOutput, 'zysd', 'index.html'), 'utf8'), 'calculator');
    assert.equal(fs.readFileSync(path.join(fixtureOutput, 'zysd', 'assets', 'app.js'), 'utf8'), 'asset');
    assert.equal(fs.existsSync(path.join(fixtureOutput, '.github')), false);
    assert.equal(fs.existsSync(path.join(fixtureOutput, 'zysd', 'src')), false);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
});

test('Pages artifact creates a root entry page when the repository has none', () => {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'zysd-pages-root-'));
  const fixtureDist = path.join(fixtureRoot, 'zysd', 'dist');
  const fixtureOutput = path.join(fixtureRoot, '_site');

  try {
    fs.mkdirSync(fixtureDist, { recursive: true });
    fs.writeFileSync(path.join(fixtureDist, 'index.html'), 'calculator', 'utf8');

    const result = spawnSync(
      process.execPath,
      [assemblePagesScript, fixtureRoot, fixtureDist, fixtureOutput],
      { encoding: 'utf8' },
    );

    assert.equal(result.status, 0, result.stderr || result.stdout);
    const rootHtml = fs.readFileSync(path.join(fixtureOutput, 'index.html'), 'utf8');
    assert.match(rootHtml, /href="\/zysd\/"/);
    assert.match(rootHtml, /江苏电力曲线计算器/);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
});
