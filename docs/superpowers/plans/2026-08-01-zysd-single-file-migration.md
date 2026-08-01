# zysd Single-File Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `zysd/index.html` the only file under `zysd` and the sole calculator entry point, while preserving all unrelated repository pages.

**Architecture:** Keep the already generated dependency-free calculator HTML unchanged and remove the obsolete React/Vite source, dependencies, build output, caches, scripts, and tests. Move the durable calculator tests at the repository root to the new URL layout and use a structure contract to prevent old files or a duplicate root entry from returning.

**Tech Stack:** Static HTML/CSS/JavaScript, Node.js built-in test runner, GitHub Pages branch publishing.

## Global Constraints

- The production calculator is `zysd/index.html` and loads no external resources.
- The repository root must not contain `index.html`.
- `zysd` must contain only `index.html`, including hidden and ignored entries.
- Preserve `.nojekyll`, root documentation and tests, and every page outside `zysd`.
- Do not run `git push`; the user pushes manually.
- Verify every recursive deletion target resolves inside the repository's exact `zysd` directory before deleting it.

---

### Task 1: Lock the new path and directory contract with tests

**Files:**
- Modify: `tests/standalone-calculator.test.mjs`
- Test: `tests/standalone-calculator.test.mjs`

**Interfaces:**
- Consumes: inline `CalculatorCore` from `zysd/index.html`.
- Produces: a test contract requiring no root `index.html` and exactly one `zysd` entry named `index.html`.

- [ ] **Step 1: Point the calculator test harness at `zysd/index.html`**

Change the page path to:

```js
const zysdDirectory = path.join(repositoryRoot, 'zysd');
const indexFile = path.join(zysdDirectory, 'index.html');
```

- [ ] **Step 2: Add the failing directory contract test**

Append:

```js
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
```

- [ ] **Step 3: Run the suite and verify the expected failure**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: existing calculation tests pass, and `calculator is published only as zysd/index.html` fails because the duplicate root file and old `zysd` entries still exist.

---

### Task 2: Remove the obsolete zysd implementation safely

**Files:**
- Preserve unchanged: `zysd/index.html`
- Delete: root `index.html`
- Delete: every `zysd` entry except `zysd/index.html`
- Modify: `tests/standalone-calculator.test.mjs`

**Interfaces:**
- Consumes: the exact current bytes of `zysd/index.html`.
- Produces: a static directory containing only `zysd/index.html`.

- [ ] **Step 1: Verify the two calculator copies are identical before cleanup**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath index.html,zysd\index.html
```

Expected: both SHA-256 hashes are identical.

- [ ] **Step 2: Resolve and validate deletion boundaries**

Resolve the repository root and `zysd` directory. Abort unless the target is exactly `<repository-root>\zysd`; enumerate all top-level entries that will be deleted and confirm `index.html` is excluded.

- [ ] **Step 3: Delete the duplicate root entry and all obsolete zysd entries**

Using native PowerShell with literal paths, remove the root `index.html` and recursively remove each validated `zysd` top-level entry except `index.html`. This includes tracked source files plus ignored `node_modules`, `dist`, `.npm-cache`, and `.vite` content.

- [ ] **Step 4: Run the standalone suite and verify green**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: all calculation, publishing, and directory-contract tests pass.

- [ ] **Step 5: Verify the retained calculator bytes and repository scope**

Run:

```powershell
Get-ChildItem -LiteralPath zysd -Force
git diff --check
git diff --name-only -- anfeng liubao
git status --short
```

Expected: `zysd` lists only `index.html`; no diff errors; no changes under `anfeng` or `liubao`; Git reports the expected old `zysd` files as deleted plus the root test modification.

---

### Task 3: Browser-verify and commit the migration

**Files:**
- Test: `zysd/index.html`
- Commit: `tests/standalone-calculator.test.mjs` and all obsolete `zysd` deletions

**Interfaces:**
- Consumes: repository-root static serving and `/zysd/index.html`.
- Produces: locally committed migration ready for the user's manual push.

- [ ] **Step 1: Serve the repository root locally**

Start a temporary static server on an unused localhost port and open `/zysd/index.html` in a real browser.

- [ ] **Step 2: Verify desktop behavior**

Confirm the exact URL ends in `/zysd/index.html`, 48 numeric inputs render, defaults are `-2.97` and `5.68`, changing the first 2026 value affects only the 2026 result, reset restores defaults, and no application console errors occur.

- [ ] **Step 3: Verify responsive and dependency-free behavior**

At a mobile viewport, confirm two input columns and no horizontal overflow. Confirm the page asset inventory contains no scripts, stylesheets, fonts, images, or other external resources.

- [ ] **Step 4: Stop the temporary server and run final automated checks**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
git diff --check
git diff --name-only -- anfeng liubao
```

Expected: all tests pass and the two Git diff checks have no output.

- [ ] **Step 5: Create the local implementation commit**

```powershell
git add -- tests/standalone-calculator.test.mjs zysd
git commit -m "refactor: keep zysd as standalone calculator"
```

The root `index.html` is untracked before cleanup and therefore needs no staging pathspec. Do not push.

- [ ] **Step 6: Hand off manual publishing**

Report the clean worktree and provide only these user-run commands:

```powershell
cd "E:\江苏国源电力交易\数据汇总2026\天气数据下载\open_meteo\marvinfight.github.io"
git push origin main
```

The published calculator URL is `https://marvinfight.github.io/zysd/index.html` after GitHub Pages completes the branch deployment.
