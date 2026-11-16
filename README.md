# ReadIN 译读

在 ReadIN 里读你文献库里的论文，读完的高亮和笔记送回文献库。适用于 Zotero 8–10。

Read the papers in your reference library with [ReadIN](https://readin.cc), then send your highlights and notes back. Works with Zotero 8–10.

> 这个插件和 Zotero 官方没有关系。Zotero 是 Corporation for Digital Scholarship 的注册商标。
> This plugin is not affiliated with or endorsed by Zotero. Zotero is a registered trademark of the Corporation for Digital Scholarship.

## 能做什么

- **在 ReadIN 打开**：右键一篇论文，或者点 PDF 阅读器顶栏的「ReadIN」按钮。
- **文献不用搬家**：ReadIN 直接看到你的分类和论文，不导入、不复制文件。
- **送回去**：在 ReadIN 画的高亮和写的随想，变成文献库里原生的高亮；AI 整理的笔记存成论文下面的一条笔记。
- 写论文照旧用文献库插引用。

## 隐私

这个版本**不连互联网**。它只在你自己的电脑上开几个入口，只回答 ReadIN 自己的网页（beta.anqapdf.app、cn-beta.anqapdf.app、anqapdf.app、readin.cc），别的网站一律拒绝。代码不混淆、没有统计。

This version makes **no internet requests**. It opens a few local endpoints on your own computer that answer only ReadIN's own pages; every other website is refused. No obfuscation, no tracking.

## 安装

1. 下载 `readin-yidu-x.y.z.xpi`。
2. 文献库软件里打开「工具 → 插件」，把文件拖进去。
3. 在 ReadIN 的文献模式里点「连接」。Chrome 会问一次是否允许访问这台电脑上的其他应用，点「允许」。

用的时候文献库软件要开着。

## 开发

- `src/bridge.js`：本机入口（列分类和论文、拿 PDF、读写高亮、写笔记）。
- `src/ui.js`：右键菜单和阅读器按钮。
- `python3 dev/test_bridge.py`：在一个隔开的测试用文献库里跑全部测试（不碰你平时用的那个）。
- `python3 build.py`：打包成 `dist/readin-yidu-x.y.z.xpi` 和 `dist/update.json`。

本机入口的规则（2026-11-16 在 Zotero 10 + Chrome 157 上确认）：
- 入口设 `allowRequestsFromUnsafeWebContent`，自己检查 `Origin`，只回答 ReadIN 的网址。
- Zotero 对 `OPTIONS` 预检不回 CORS 头，所以只用不需要预检的请求：GET，和不设类型的 POST（正文是 JSON 文字）。
- Zotero 的本机服务只能回文字，PDF 用 base64url 传。
- Chrome 从网站访问本机要用户允许一次（本机网络权限）。

## 许可证

AGPL-3.0。插件免费、开源；第二步会加上用 ReadIN 账户额度的 AI 功能，收费判断都在 ReadIN 的服务器上，插件里没有任何密钥。
