# Standalone HTML Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the Jiangsu electricity curve calculator as one dependency-free root `index.html` that GitHub Pages can serve directly from `main`.

**Architecture:** Keep the existing React implementation under `zysd` as a reference and historical fallback. Add a self-contained root page with two inline scripts: a pure, testable `CalculatorCore` API and a DOM adapter that renders inputs and updates results. Retire the custom Pages workflow so repository-root branch publishing has a single deployment source.

**Tech Stack:** HTML5, inline CSS, browser JavaScript, Node.js built-in test runner and `node:vm`, GitHub Pages branch publishing.

## Global Constraints

- The production page is one repository-root `index.html`; it must not load local or remote scripts, styles, fonts, APIs, or images.
- Preserve the current blue-and-white interface, responsive layout, 48 hourly inputs, default values, real-time results, and reset behavior.
- Copy every numeric curve value exactly from `zysd/src/App.tsx`; do not round source data.
- Keep `zysd` React source available as a fallback and do not modify files under `anfeng` or `liubao`.
- The agent may create local commits but must never run `git push`; the user pushes manually.
- The public URL becomes `https://marvinfight.github.io/` after the user selects `main` and `/(root)` as the Pages branch source.

---

## File Map

- Create `index.html`: the complete production calculator, including CSS, data, pure calculations, markup rendering, and event handling.
- Create `.nojekyll`: instruct branch-based GitHub Pages to serve repository files without Jekyll processing.
- Create `tests/standalone-calculator.test.mjs`: validate the inline core API, calculation parity, self-contained page contract, and branch-publishing layout.
- Modify `zysd/tests/build-output.test.mjs:1-152`: retain the two historical Vite output tests and remove the three tests tied to the retired custom Pages workflow.
- Delete `.github/workflows/deploy.yml`: prevent the old Actions deployment from competing with branch-based Pages publishing.
- Preserve `zysd/src/App.tsx`, `zysd/src/styles.css`, and `zysd/scripts/assemble-pages.mjs` unchanged as reference and fallback material.

---

### Task 1: Add the standalone calculation core

**Files:**
- Create: `tests/standalone-calculator.test.mjs`
- Create: `index.html`

**Interfaces:**
- Consumes: exact constants from `zysd/src/App.tsx:5-42`.
- Produces: `globalThis.CalculatorCore`, frozen with:
  - `defaults.noPv2026: readonly number[]`
  - `defaults.customer2027: readonly number[]`
  - `calculate(noPv2026: Array<number|string>, customer2027: Array<number|string>): { curve2026: number|null, curve2027: number|null }`
  - `formatNumber(value: number|null): string`

- [ ] **Step 1: Write the failing core tests**

Create `tests/standalone-calculator.test.mjs` with this test harness and three tests:

```js
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
const indexFile = path.join(repositoryRoot, 'index.html');

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
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run from the repository root:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: FAIL with `ENOENT` for the missing root `index.html`.

- [ ] **Step 3: Create the minimal self-contained page and core API**

Create a valid UTF-8 `index.html` with `<html lang="zh-CN">`, viewport metadata, the title `江苏电力曲线计算器`, an empty `<main id="app"></main>`, and an inline `<script id="calculator-core">`.

Inside that script:

1. Copy `MARKET_CURVE_2026`, `PROVINCE_LOAD`, `DELTA_2027`, `DEFAULT_NO_PV_2026`, and `DEFAULT_CUSTOMER_2027` exactly from `zysd/src/App.tsx:5-42`.
2. Implement and expose this core without TypeScript syntax:

```js
(() => {
  'use strict';

  const marketCurve2027 = MARKET_CURVE_2026.map(
    (value, index) => value + DELTA_2027[index],
  );

  function toNumbers(values) {
    return values.map((value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    });
  }

  function weightedPrice(priceCurve, loadCurve) {
    const totalLoad = loadCurve.reduce((total, value) => total + value, 0);
    if (totalLoad === 0) return null;

    return priceCurve.reduce(
      (total, price, index) => total + price * (loadCurve[index] / totalLoad),
      0,
    );
  }

  function calculate(noPv2026, customer2027) {
    const province2026 = weightedPrice(MARKET_CURVE_2026, PROVINCE_LOAD);
    const customer2026 = weightedPrice(MARKET_CURVE_2026, toNumbers(noPv2026));
    const province2027 = weightedPrice(marketCurve2027, PROVINCE_LOAD);
    const weighted2027 = weightedPrice(marketCurve2027, toNumbers(customer2027));

    return {
      curve2026:
        province2026 === null || customer2026 === null
          ? null
          : province2026 - customer2026,
      curve2027:
        province2027 === null || weighted2027 === null
          ? null
          : province2027 - weighted2027,
    };
  }

  function formatNumber(value) {
    return value === null || !Number.isFinite(value)
      ? '--'
      : value.toLocaleString('zh-CN', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
  }

  globalThis.CalculatorCore = Object.freeze({
    defaults: Object.freeze({
      noPv2026: Object.freeze([...DEFAULT_NO_PV_2026]),
      customer2027: Object.freeze([...DEFAULT_CUSTOMER_2027]),
    }),
    calculate,
    formatNumber,
  });
})();
```

- [ ] **Step 4: Run the core tests and verify they pass**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: 3 tests PASS with default display values `-2.97` and `5.68`.

- [ ] **Step 5: Commit the core and tests**

```powershell
git add -- index.html tests/standalone-calculator.test.mjs
git commit -m "feat: add standalone calculator core"
```

---

### Task 2: Add the complete responsive calculator interface

**Files:**
- Modify: `tests/standalone-calculator.test.mjs`
- Modify: `index.html`

**Interfaces:**
- Consumes: `globalThis.CalculatorCore` from Task 1.
- Produces DOM IDs `result-2026`, `result-2027`, `curve-2026`, `curve-2027`, and `reset-button`; produces 48 inputs with `data-curve` and numeric `data-index` attributes.

- [ ] **Step 1: Add the failing page-contract test**

Append this test to `tests/standalone-calculator.test.mjs`:

```js
test('root page contains the complete interface and no external dependencies', () => {
  const html = readPage();

  for (const expected of [
    '江苏电力曲线计算器',
    '2026 曲线优势/均价',
    '2027 曲线优势/均价',
    '2026 无光伏客户负荷曲线',
    '2027 客户负荷曲线',
    'id="result-2026"',
    'id="result-2027"',
    'id="curve-2026"',
    'id="curve-2027"',
    'id="reset-button"',
  ]) {
    assert.ok(html.includes(expected), `Expected page to include ${expected}.`);
  }

  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /<link[^>]+rel=["']stylesheet["']/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});
```

- [ ] **Step 2: Run the page test and verify it fails**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: the three core tests PASS and the new interface test FAILS because the controls are missing.

- [ ] **Step 3: Inline the current visual design**

Add a `<style>` element to `index.html`. Copy the rules from `zysd/src/styles.css` and retain these exact responsive breakpoints:

```css
@media (max-width: 1120px) {
  .curve-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .app-shell { width: min(100% - 20px, 1320px); margin: 10px auto; padding: 22px 16px; border-radius: 12px; }
  .topbar, .result-strip { align-items: stretch; flex-direction: column; }
  .reset-button { width: 100%; }
  .curve-panel { padding: 18px 14px; }
  .panel-heading { align-items: flex-start; flex-direction: column; gap: 8px; }
  .curve-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 10px; }
}
```

Keep system fonts only: `Inter`, `Microsoft YaHei`, `PingFang SC`, and `system-ui`. Do not add web-font URLs.

- [ ] **Step 4: Add semantic markup and the DOM adapter**

Replace the empty app container with the current header, result strip, and two curve panels. The panels must contain empty grid containers `curve-2026` and `curve-2027`; the second inline script generates their inputs.

Use this state and event flow in the second inline script:

```js
(() => {
  'use strict';

  const core = globalThis.CalculatorCore;
  const state = {
    noPv2026: [...core.defaults.noPv2026],
    customer2027: [...core.defaults.customer2027],
  };

  function toInput(value) {
    return Number(value).toFixed(4).replace(/\.?0+$/, '');
  }

  function renderInputs(containerId, curveName, label, values) {
    const container = document.getElementById(containerId);
    container.replaceChildren();

    values.forEach((value, index) => {
      const hour = String(index + 1).padStart(2, '0');
      const wrapper = document.createElement('label');
      wrapper.className = 'hour-input';

      const caption = document.createElement('span');
      caption.textContent = `${hour}:00`;

      const input = document.createElement('input');
      input.type = 'number';
      input.inputMode = 'decimal';
      input.value = toInput(value);
      input.dataset.curve = curveName;
      input.dataset.index = String(index);
      input.setAttribute('aria-label', `${label} ${hour}:00`);

      wrapper.append(caption, input);
      container.append(wrapper);
    });
  }

  function renderResults() {
    const result = core.calculate(state.noPv2026, state.customer2027);
    document.getElementById('result-2026').textContent = core.formatNumber(result.curve2026);
    document.getElementById('result-2027').textContent = core.formatNumber(result.curve2027);
  }

  function renderAll() {
    renderInputs(
      'curve-2026',
      'noPv2026',
      '2026 无光伏客户负荷曲线',
      state.noPv2026,
    );
    renderInputs(
      'curve-2027',
      'customer2027',
      '2027 客户负荷曲线',
      state.customer2027,
    );
    renderResults();
  }

  document.getElementById('app').addEventListener('input', (event) => {
    const input = event.target.closest('input[data-curve][data-index]');
    if (!input) return;
    state[input.dataset.curve][Number(input.dataset.index)] = input.value;
    renderResults();
  });

  document.getElementById('reset-button').addEventListener('click', () => {
    state.noPv2026 = [...core.defaults.noPv2026];
    state.customer2027 = [...core.defaults.customer2027];
    renderAll();
  });

  renderAll();
})();
```

- [ ] **Step 5: Run tests and browser smoke checks**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
python -m http.server 4173 --directory .
```

Open `http://127.0.0.1:4173/` in a real browser and verify:

- exactly 48 numeric inputs render;
- the default cards show `-2.97` and `5.68`;
- changing the first 2026 input changes only the 2026 result;
- `恢复默认值` restores the original value and result;
- a 390 × 844 viewport shows two input columns without horizontal scrolling.

Stop the local server after the checks.

- [ ] **Step 6: Commit the complete interface**

```powershell
git add -- index.html tests/standalone-calculator.test.mjs
git commit -m "feat: add standalone calculator interface"
```

---

### Task 3: Retire custom deployment and validate branch publishing

**Files:**
- Create: `.nojekyll`
- Modify: `tests/standalone-calculator.test.mjs`
- Modify: `zysd/tests/build-output.test.mjs:1-152`
- Delete: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: root `index.html` from Tasks 1 and 2.
- Produces: a repository layout compatible with GitHub Pages `main` / `/(root)` branch publishing and no custom deployment workflow.

- [ ] **Step 1: Add the failing publishing-layout test**

Append this test to `tests/standalone-calculator.test.mjs`:

```js
test('repository is ready for branch-based GitHub Pages publishing', () => {
  assert.equal(fs.existsSync(path.join(repositoryRoot, '.nojekyll')), true);
  assert.equal(
    fs.existsSync(path.join(repositoryRoot, '.github', 'workflows', 'deploy.yml')),
    false,
  );
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: the publishing-layout test FAILS because `.nojekyll` is absent and the custom workflow still exists.

- [ ] **Step 3: Switch the repository to static branch publishing**

Create an empty root `.nojekyll` and delete `.github/workflows/deploy.yml`.

In `zysd/tests/build-output.test.mjs`:

- remove imports `os` and `spawnSync`;
- remove constants `repositoryRoot`, `pagesWorkflowFile`, and `assemblePagesScript`;
- delete the three tests beginning at the current lines 71, 94, and 129;
- retain the two tests for the historical Vite build output.

Do not delete `zysd/scripts/assemble-pages.mjs`; it remains part of the fallback implementation documented in the design.

- [ ] **Step 4: Run all relevant automated checks**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
pnpm.cmd --dir zysd run build
node --test zysd\tests\build-output.test.mjs
git diff --check
git diff --name-only -- anfeng liubao
```

Expected:

- standalone suite: 5 tests PASS;
- historical Vite build: succeeds;
- historical build-output suite: 2 tests PASS;
- `git diff --check`: no errors;
- legacy HTML diff command: no output.

- [ ] **Step 5: Perform final browser verification**

Serve the repository root and repeat the desktop and 390 × 844 checks from Task 2. In addition, set all 24 values in one curve to `0` and verify its result becomes `--` without console errors.

- [ ] **Step 6: Review and commit deployment changes**

Confirm `git status --short` lists only:

```text
 D .github/workflows/deploy.yml
?? .nojekyll
 M zysd/tests/build-output.test.mjs
```

The already committed Task 1 and Task 2 files should not appear. Then commit:

```powershell
git add -- .nojekyll .github/workflows/deploy.yml zysd/tests/build-output.test.mjs
git commit -m "chore: switch Pages to branch publishing"
```

---

### Task 4: Hand off the manual GitHub Pages switch

**Files:**
- No repository changes.

**Interfaces:**
- Consumes: the three local implementation commits and the existing `main` branch.
- Produces: clear manual instructions; the user remains responsible for pushing and changing GitHub settings.

- [ ] **Step 1: Verify the local handoff state**

Run:

```powershell
git status --short
git log -4 --oneline
```

Expected: clean working tree and recent local commits for the design, core/interface, and branch-publishing switch.

- [ ] **Step 2: Give the user the manual push command**

Provide, but do not run:

```powershell
cd "E:\江苏国源电力交易\数据汇总2026\天气数据下载\open_meteo\marvinfight.github.io"
git push origin main
```

- [ ] **Step 3: Give the exact Pages settings**

After the user pushes, instruct them to open repository `Settings` → `Pages` and set:

```text
Source: Deploy from a branch
Branch: main
Folder: /(root)
```

After saving and waiting for deployment, the calculator URL is:

```text
https://marvinfight.github.io/
```

Remind the user that the single-file change removes build-related failure modes but does not guarantee `github.io` connectivity from every Chinese mainland network.
