# 负荷曲线预览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live SVG preview for each customer load curve, relabel the result unit, and clear both curves to zero from the reset control.

**Architecture:** Keep the existing zero-dependency single-page architecture. The UI script will render a reusable SVG line chart from each 24-value state array after input and reset events; calculation logic remains in `CalculatorCore`.

**Tech Stack:** HTML, CSS, browser-native JavaScript, SVG, Node.js test runner, Playwright browser checks.

## Global Constraints

- Modify only `index.html` and focused browser checks; add no runtime dependency.
- Preserve the two existing 24-hour inputs and weighted-price formula.
- Render the preview with accessible native SVG markup.
- Reset both load arrays to exactly twenty-four numeric zeroes.

---

### Task 1: Add test coverage for requested UI contract

**Files:**
- Create: `tests/index.test.js`
- Test: `tests/index.test.js`

**Interfaces:**
- Consumes: `index.html` rendered in a browser.
- Produces: automated checks for result wording, chart rendering, live data updates, and zero reset.

- [ ] Write the failing browser test for two preview containers, updated “曲线优势 /厘” wording, a populated SVG polyline after input, and 48 zero inputs after reset.
- [ ] Run `npx playwright test tests/index.test.js` and verify it fails because charts and the new label do not yet exist.

### Task 2: Implement native SVG previews and zero reset

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `state.noPv2026` and `state.customer2027`, each a 24-item load array.
- Produces: `renderCurveChart(containerId, values, label)`, which writes one labelled SVG polyline preview.

- [ ] Add a `.curve-chart` container after each input grid and responsive styling for a 190 px high SVG.
- [ ] Implement `renderCurveChart` using 24 evenly spaced x coordinates and an independent zero-safe y scale.
- [ ] Call chart rendering at initial render, after the matching input event, and after reset.
- [ ] Change both result labels to “曲线优势 /厘”.
- [ ] Replace the two default-array assignments in the reset handler with `Array(24).fill(0)`.

### Task 3: Verify browser behavior and responsive layout

**Files:**
- Test: `tests/index.test.js`
- Modify: `index.html` only if verification identifies a layout or accessibility issue.

**Interfaces:**
- Consumes: completed page and browser test.
- Produces: evidence of correct behavior at desktop and narrow widths.

- [ ] Run `npx playwright test tests/index.test.js`; expected result is PASS with correct labels, two previews, dynamic SVG data and a zero reset.
- [ ] Inspect 1280 px and 390 px browser views; expected result is readable, non-overflowing charts without console errors.
- [ ] Commit the completed implementation with `git commit -m "feat: add live load curve previews"`.
