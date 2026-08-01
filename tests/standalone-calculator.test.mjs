import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
);
const zysdDirectory = path.join(repositoryRoot, 'zysd');
const indexFile = path.join(zysdDirectory, 'index.html');

function readPage() {
  return fs.readFileSync(indexFile, 'utf8');
}

function extractInlineScript(html, id) {
  const match = html.match(
    new RegExp(`<script\\s+id=["']${id}["'][^>]*>([\\s\\S]*?)<\\/script>`),
  );
  assert.ok(match, `Expected inline script #${id}.`);
  return match[1];
}

function loadCalculatorCore() {
  const context = vm.createContext({ Intl });
  vm.runInContext(extractInlineScript(readPage(), 'calculator-core'), context);
  return context.CalculatorCore;
}

function assertClose(actual, expected) {
  assert.ok(
    Math.abs(actual - expected) < 1e-12,
    `Expected ${actual} to equal ${expected}.`,
  );
}

test('standalone core reproduces current default results', () => {
  const core = loadCalculatorCore();
  const result = core.calculate(
    core.defaults.noPv2026,
    core.defaults.customer2027,
  );

  assertClose(result.curve2026, -2.96731698384923);
  assertClose(result.curve2027, 5.684334381148005);
  assert.equal(core.formatNumber(result.curve2026), '-2.97');
  assert.equal(core.formatNumber(result.curve2027), '5.68');
});

test('standalone core treats blank and invalid values as zero', () => {
  const core = loadCalculatorCore();
  const emptyCurve = Array.from({ length: 24 }, () => '');
  const invalidCurve = Array.from({ length: 24 }, () => 'not-a-number');

  assert.equal(core.calculate(emptyCurve, core.defaults.customer2027).curve2026, null);
  assert.equal(core.calculate(core.defaults.noPv2026, invalidCurve).curve2027, null);
  assert.equal(core.formatNumber(null), '--');
});

test('standalone core recalculates after an input changes', () => {
  const core = loadCalculatorCore();
  const changed = [...core.defaults.noPv2026];
  changed[0] = 0;

  const original = core.calculate(
    core.defaults.noPv2026,
    core.defaults.customer2027,
  );
  const updated = core.calculate(changed, core.defaults.customer2027);

  assert.notEqual(updated.curve2026, original.curve2026);
  assertClose(updated.curve2027, original.curve2027);
});

test('repository is ready for branch-based GitHub Pages publishing', () => {
  assert.equal(
    fs.existsSync(path.join(repositoryRoot, '.nojekyll')),
    true,
    'Expected a root .nojekyll file for direct static publishing.',
  );
  assert.equal(
    fs.existsSync(path.join(repositoryRoot, '.github', 'workflows', 'deploy.yml')),
    false,
    'Expected the competing custom Pages workflow to be removed.',
  );
});

test('calculator is published only as zysd/index.html', () => {
  assert.equal(
    fs.existsSync(path.join(repositoryRoot, 'index.html')),
    false,
    'Expected the duplicate root index.html to be absent.',
  );
  assert.deepEqual(
    fs.readdirSync(zysdDirectory, { withFileTypes: true })
      .map((entry) => entry.name)
      .sort(),
    ['index.html'],
  );
});
