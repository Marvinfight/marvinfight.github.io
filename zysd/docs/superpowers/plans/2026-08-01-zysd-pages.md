# ZYSD GitHub Pages 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将江苏电力曲线计算器发布为部署在 `/zysd/` 的静态 GitHub Pages 应用。

**Architecture:** 使用 Vite 将 React 单页应用构建至 `dist/`；`base` 固定为 `/zysd/`。计算逻辑运行在浏览器，GitHub Actions 上传并部署构建目录。

**Tech Stack:** React 19、TypeScript、Vite 8、GitHub Actions、Node.js 22。

## Global Constraints

- 部署 URL 必须为 `https://marvinfight.github.io/zysd/`。
- 不得保留 Cloudflare Worker、D1、Vinext 或 Next.js 服务端运行时依赖。
- 计算器须保留两组 24 小时曲线输入、实时结果和恢复默认值功能。

---

### Task 1: 静态应用基础与构建测试

**Files:**
- Create: `package.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/styles.css`, `tests/build-output.test.mjs`
- Create: `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, `.gitignore`

- [ ] **Step 1: Write the failing test**

```js
test('build creates an HTML entry whose assets use the project base path', () => {
  assert.match(readFileSync('dist/index.html', 'utf8'), /src="\/zysd\/assets\//);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/build-output.test.mjs`
Expected: FAIL because `dist/index.html` does not exist.

- [ ] **Step 3: Write minimal implementation**

```ts
export default defineConfig({ base: '/zysd/', plugins: [react()] });
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run build && node --test tests/build-output.test.mjs`
Expected: PASS with `/zysd/assets/` in the generated entry page.

- [ ] **Step 5: Commit**

```bash
git add package.json index.html src vite.config.ts tsconfig*.json tests .gitignore
git commit -m "feat: add static Vite app foundation"
```

### Task 2: 曲线计算器和界面

**Files:**
- Modify: `src/App.tsx`, `src/styles.css`
- Test: `tests/build-output.test.mjs`

- [ ] **Step 1: Write the failing test**

```js
test('built page contains the curve calculator title', () => {
  assert.match(readFileSync('dist/index.html', 'utf8'), /江苏电力曲线计算器/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run build && node --test tests/build-output.test.mjs`
Expected: FAIL because the new calculator title is absent.

- [ ] **Step 3: Write minimal implementation**

```tsx
export default function App() {
  return <main className="app-shell"><h1>江苏电力曲线计算器</h1></main>;
}
```

Add the existing weighted-price calculation, the two editable 24-hour curves, result cards, reset behavior, and responsive semantic styles.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run build && node --test tests/build-output.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add responsive curve calculator"
```

### Task 3: GitHub Pages deployment

**Files:**
- Create: `.github/workflows/deploy.yml`
- Modify: `README.md`, `tests/build-output.test.mjs`

- [ ] **Step 1: Write the failing test**

```js
test('deployment workflow uploads and deploys the static site', () => {
  const workflow = readFileSync('.github/workflows/deploy.yml', 'utf8');
  assert.match(workflow, /actions\/upload-pages-artifact/);
  assert.match(workflow, /actions\/deploy-pages/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/build-output.test.mjs`
Expected: FAIL because the workflow is absent.

- [ ] **Step 3: Write minimal implementation**

```yaml
on:
  push:
    branches: [main]
permissions:
  pages: write
  id-token: write
```

Add Node 22 setup, `npm ci`, `npm run build`, artifact upload of `dist`, and GitHub Pages deployment. Document the first-time Pages setting in README.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run build && node --test tests/build-output.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github README.md tests
git commit -m "ci: deploy site to GitHub Pages"
```
