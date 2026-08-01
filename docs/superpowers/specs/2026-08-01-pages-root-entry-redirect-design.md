# GitHub Pages 根入口跳转设计

## 目标

为从 `main` 分支 `/(root)` 发布的 GitHub Pages 恢复根目录入口，使站点能够被 Pages 正常识别，同时保持计算器唯一生产文件为 `zysd/index.html`。

## 已确认方案

在仓库根目录新增一个最小的 `index.html`。页面通过相对地址 `./zysd/index.html` 立即跳转，并显示一个可点击的后备链接。相对地址既适用于本地静态服务器，也适用于 `https://marvinfight.github.io/`。

考虑过但不采用的方案：

- 制作根目录导航首页：会增加不必要的界面和维护内容。
- 改为从 `/docs` 发布：需要移动现有页面并改变仓库结构，风险更高。

## 文件边界

- 新增 `index.html`：仅负责跳转，不包含计算器逻辑。
- 保持 `zysd/index.html` 字节不变，继续承载全部计算功能。
- 保持 `anfeng`、`liubao` 及仓库内其他 HTML 页面不变。
- 更新根测试，验证根入口会跳转到 `./zysd/index.html`，并继续验证 `zysd` 目录只有一个文件。

## 验收标准

1. 根目录存在 `index.html`。
2. 打开根地址会进入 `/zysd/index.html`。
3. 直接打开 `/zysd/index.html` 仍显示并运行计算器。
4. `zysd` 目录仍只包含 `index.html`。
5. 不修改其他 HTML 页面，不执行 `git push`。
