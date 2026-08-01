# zysd 单文件迁移设计

## 目标

将计算器固定发布在 `https://marvinfight.github.io/zysd/index.html`，并删除 `zysd` 中旧 React/Vite 实现及其本地构建产物。

## 最终结构

- `zysd/index.html`：唯一的计算器生产文件，保留当前单文件页面的全部样式、数据和计算功能。
- 根目录不再保留 `index.html`，避免出现两个需要同步维护的计算器入口。
- 根目录 `.nojekyll`、测试、设计文档以及 `anfeng`、`liubao` 等现有页面保持不变。

## 删除范围

删除 `zysd` 中除 `index.html` 外的所有内容，包括旧源码、配置、构建脚本、旧测试、依赖目录、构建输出和缓存。特别清理已经误提交的 `zysd/.vite/deps` 文件。

## 测试与发布

- 根目录的计算器测试改为读取 `zysd/index.html`。
- 增加目录结构约束：根目录不得存在 `index.html`，`zysd` 顶层及子目录中只能存在 `index.html`。
- 验证默认结果、输入变化、零负荷和恢复默认值等浏览器行为。
- GitHub Pages 继续使用 `main` 分支的 `/(root)` 发布；用户手动 `push`，不使用自动推送。

## 成功标准

1. `zysd` 目录只包含 `index.html`。
2. `https://marvinfight.github.io/zysd/index.html` 可直接加载计算器。
3. 页面不依赖构建工具或外部资源。
4. 仓库其他 HTML 页面未发生变化。
