# ZYSD GitHub Pages 设计

## 目标

将现有江苏电力曲线计算器迁移为可发布到 `https://marvinfight.github.io/zysd/` 的纯静态网站，同时改善工具界面的可读性与移动端体验。

## 架构

采用 Vite + React 客户端构建；不保留 Vinext、Cloudflare Worker、D1 或服务端渲染依赖。`vite.config.ts` 将 `base` 设为 `/zysd/`，使全部构建产物在 GitHub Pages 项目子路径中可用。GitHub Actions 在推送 `main` 后构建并部署 `dist/`。

## 页面

保留现有曲线计算逻辑和数据输入。页面重构为清晰的工具布局：顶部标题与说明、参数输入区、结果摘要和曲线结果区；统一深蓝/青色强调色、可辨识的聚焦和错误状态，并在窄屏单栏显示。

## 验证

构建结果不包含服务端入口或 Node 运行时依赖；自动化测试检查构建产物中存在入口 HTML、页面资源引用带有 `/zysd/` 前缀，且部署工作流使用 GitHub Pages 官方 actions。浏览器中验证计算器的主要输入和结果更新。
