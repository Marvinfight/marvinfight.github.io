# GitHub Pages Root Entry Redirect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the repository-root GitHub Pages entry and redirect it to the standalone calculator at `zysd/index.html`.

**Architecture:** Add a minimal root `index.html` containing an immediate relative redirect and a visible fallback link. Keep the calculator and every unrelated HTML page unchanged, and protect the redirect with a Node.js behavior test.

**Tech Stack:** Static HTML, inline JavaScript, Node.js built-in test runner, GitHub Pages branch publishing.

## Global Constraints

- `zysd/index.html` remains the only file under `zysd` and is not modified.
- The root entry redirects to `./zysd/index.html`.
- No files under `anfeng` or `liubao` are modified.
- Do not run `git push`; the user pushes manually.

---

### Task 1: Protect the Pages entry behavior

**Files:**
- Modify: `tests/standalone-calculator.test.mjs`
- Create: `index.html`

**Interfaces:**
- Consumes: the root page's inline script identified by `pages-redirect`.
- Produces: a browser-visible redirect to `./zysd/index.html`.

- [ ] **Step 1: Write the failing redirect behavior test**

Read the root page, execute its `pages-redirect` script with a controlled `window.location.replace`, and assert that the observed destination is `./zysd/index.html`. Keep the existing `zysd` single-file directory assertion.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: the redirect test fails because root `index.html` does not exist.

- [ ] **Step 3: Add the minimal root entry**

Create an accessible static page with:

```html
<script id="pages-redirect">
  window.location.replace('./zysd/index.html');
</script>
```

Also include a zero-delay HTML refresh and a visible link to the same relative destination for script-disabled browsers.

- [ ] **Step 4: Run the test and verify GREEN**

Run:

```powershell
node --test tests\standalone-calculator.test.mjs
```

Expected: all tests pass.

- [ ] **Step 5: Browser-verify and commit locally**

Serve the repository root, verify `/` redirects to `/zysd/index.html`, verify the calculator renders, check console health, then run:

```powershell
git diff --check
git diff --name-only -- anfeng liubao
git add -- index.html tests/standalone-calculator.test.mjs docs/superpowers/specs/2026-08-01-pages-root-entry-redirect-design.md docs/superpowers/plans/2026-08-01-pages-root-entry-redirect.md
git commit -m "fix: restore GitHub Pages root entry"
```

Do not push.
