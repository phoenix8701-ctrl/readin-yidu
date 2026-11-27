# ReadIN 译读

**English:** ReadIN for Zotero — read your Zotero papers in ReadIN (side-by-side translation, AI that explains the paper), and your highlights and notes come back to Zotero. [Read in English ↓](#english)

在 Zotero 里点一下，用 ReadIN 读论文：整页中英对照、AI 讲清这篇说了什么；读完的高亮和笔记自动回到 Zotero。

> **内测中，点这个链接就能用 AI**：[领内测资格](https://beta.anqapdf.app/#ref=cze3sewgik)。不用注册、不用填东西，打开 ReadIN 就自动配好（每月名额有限，领完了下个月再来）。
> **在中国大陆？** 用大陆版：[领大陆版内测资格](https://cn-beta.anqapdf.app/#invite=CN-T294-ZYYF-E8P6&from=zotero)（AI 用 DeepSeek，在大陆能直接用）。
> 读论文、高亮、笔记回到 Zotero 不用领也能用。

![演示：Zotero 里打开 → 整页中英对照 → 在译文上划线，原文跟着划 →「我不想读」→ 高亮回到 Zotero](docs/demo.gif)

## 为什么用它

- **整页中英对照**：不用一句一句选。整页翻好，原文和译文对着读；在译文上划一句，原文里对应的那句也一起划上。
- **「我不想读，告诉我说了啥」**：一句话让 AI 讲清这篇论文说了什么，摘出关键观点，点一下跳回原文那一句。
- **不用自己弄 API 密钥**：不用去申请 OpenAI、Claude 的密钥，也不用填设置。内测期间点上面的链接就行，正式版登录就能用。
- **导出思维导图**：AI 把你的高亮和想法整理成一张思维导图，能折叠、能「遮住回想」，发给别人双击就能打开。
- **随时问 AI**：选中任何一句都能问，讲术语、拆长句、问这一段在全文里起什么作用。ReadIN 在电脑和 iPad 上都能用。
- **文献不搬家**：Zotero 照旧管文献和引用。在 ReadIN 画的高亮、写的想法变成 Zotero 自己的批注；AI 整理的笔记存成论文下面的一条笔记。
- **译文存回 Zotero**：翻译过的论文一键导出成译文 PDF（版式和原文一样，图表公式都不动），也可以要中英对照 PDF，存成这篇论文下面的附件，在 Zotero 里就能读、能批注。

## 三步装好

1. **下载插件**：[点这里下载](https://readin.cc/yidu/readin-yidu.xpi)，电脑的「下载」文件夹里会多一个 `readin-yidu.xpi` 文件。在中国大陆从[这里下载](https://cn-beta.anqapdf.app/yidu/readin-yidu.xpi)更快。
2. **拖进 Zotero**：打开 Zotero，点菜单「工具 → 插件」，把刚下载的文件拖进弹出来的窗口。列表里出现「ReadIN 译读」，就装好了。
   找不到「工具」？Mac 上它在屏幕最顶上那一排菜单里；Windows 上在 Zotero 窗口的顶上。
   拖不进去（鼠标变成 🚫）？在那个窗口右上角点齿轮 ⚙，选「从文件安装插件…」（英文界面叫 Install Plugin From File…），再选刚下载的文件。
3. **打开 ReadIN**：用 Chrome 或 Edge 点[打开 ReadIN（AI 已配好）](https://beta.anqapdf.app/#ref=cze3sewgik)；在中国大陆点[打开大陆版](https://cn-beta.anqapdf.app/#invite=CN-T294-ZYYF-E8P6&from=zotero)。点最上面的「连接 Zotero」；Chrome 问能不能访问本机网络，点「允许」。
   Mac 上的 Safari 连不了 Zotero（Safari 不让网页连电脑上的 Zotero），请用 Chrome 或 Edge。
   以前用过 ReadIN？右上角选「文献」，书架上点「连接 Zotero」。

**装好以后，两种方法都能打开一篇论文：**

- 在文库里**右键**一篇论文，选「在 ReadIN 打开」（繁体中文的 Zotero 里叫「在 ReadIN 中開啟」，日语的叫「ReadIN で開く」，英文的叫「Open in ReadIN」）；
- 已经在 Zotero 里看这篇论文了？直接点顶栏右边的「**ReadIN**」。

**网页快照也行（插件 0.7 起）：** 没有 PDF、只存了网页快照的条目（比如用浏览器扩展翻好再存进 Zotero 的网页），一样右键「在 ReadIN 打开」，或者打开快照点顶栏的「ReadIN」。ReadIN 把它整理成干净的正文，左边是大纲，扩展翻好的中文照样显示；高亮和想法写进这篇下面的「ReadIN 笔记」。

**改论文名（插件 0.8 起）：** Zotero 认出来的论文名不准时，在 ReadIN 书架「文献」看法里鼠标停在那一行、点标题旁的「✎」改，Zotero 里那一条跟着改（「书目」窗口里改作者、年份也一样，只写改了的那几项）。

读的时候 Zotero 要开着。

## 要知道的

- **两边都要开着**：ReadIN 和 Zotero 在你自己的电脑上直接连，不经过网络，所以要同时开着、在同一台电脑上。Zotero 里新画的高亮、框选（框公式、图表的方框）、便签、文本框、手绘，下次在 ReadIN 打开这篇时带过来（框选、便签、文本框在 ReadIN 里改了也会存回 Zotero，插件 0.6 起）。
- **用哪个浏览器打开**：插件会记住你平时用 ReadIN 的浏览器（在那里配好了 ReadIN、连过 Zotero 的那个），「在 ReadIN 打开」就用它打开，不是电脑的默认浏览器（0.4 起；Windows、Mac 上的 Edge、Chrome、Firefox、Safari 等）。还没记住、或者打不开那个浏览器时，用电脑的默认浏览器。
- **支持**：Zotero 9、10；电脑上的 Chrome 或 Edge（Safari 用不了）。国际版的 AI 用 Claude，大陆版用 DeepSeek；在中国大陆请用大陆版（插件在大陆的时区会默认打开大陆版）。
- **更新**：插件会自己更新：Zotero 每次打开时看一下有没有新版，有就装好，不用重启。想马上更新：Zotero 里「工具 → 插件」，点右上角的齿轮 →「检查更新」。ReadIN 发现插件太旧时，也会提醒你、能直接点「现在更新」（0.3 起）。
- **隐私**：插件只回答 ReadIN 自己的网页，别的网站一律拒绝。它唯一连互联网的是检查新版：Zotero 打开时去 readin.cc 看一下有没有新版插件（和 Zotero 平时检查插件更新一样，不带你的文献和笔记）。代码开源、不混淆、没有统计。用 AI 功能时，你要翻译或提问的文字会经过 ReadIN 的服务发给 AI。
- **收费**：插件免费。ReadIN 正式版有免费额度，用得多可以升级。

## 想聊聊

用着有问题、有想法，都可以找我：

- 微信：扫下面的二维码
- 邮箱：Phoenix@anqalabs.org

<img src="docs/wechat-qr.jpg" alt="微信二维码" width="200">

ReadIN 里左下角的「吐槽一下」也能直接写给我，我在后台看得到、会回复。

> 这个插件和 Zotero 官方没有关系。Zotero 是 Corporation for Digital Scholarship 的注册商标。

---

## English

**Read your Zotero papers in ReadIN: full-page side-by-side translation, AI that tells you what a paper says, and your highlights and notes flow back into Zotero.**

> **In beta — one click to try the AI features**: [get beta access](https://beta.anqapdf.app/#ref=cze3sewgik). No sign-up: ReadIN opens with AI ready (limited places each month). Reading, highlighting and syncing back to Zotero work without it.

- **Full-page side-by-side translation**: no selecting sentence by sentence. Highlight a sentence in the translation and the matching sentence in the original is highlighted too.
- **"I don't want to read it, tell me what it says"**: AI explains the paper and pulls out key points; click one to jump to the sentence.
- **No API keys to set up**: no OpenAI or Claude keys, no settings. Use the link above during the beta; sign in once it launches.
- **Mind map export**: AI turns your highlights and thoughts into a foldable mind map you can share.
- **Ask AI anywhere**: select any sentence and ask. ReadIN works on desktop and iPad.
- **Your library stays in Zotero**: highlights and notes become native Zotero annotations and a child note.
- **Translated PDF back into Zotero**: export a translated paper as a PDF with the original layout (figures and formulas untouched), or a side-by-side PDF, saved as an attachment under the same paper.

**Set up in three steps**:

1. [Download the plugin](https://readin.cc/yidu/readin-yidu.xpi). A file called `readin-yidu.xpi` lands in your Downloads folder.
2. Open Zotero, choose Tools → Plugins from the menu, and drag the file into the window. When "ReadIN 译读" shows up in the list, it's installed. If it won't drop (you see a 🚫), click the gear ⚙ at the top right of that window, choose Install Plugin From File…, and pick the file you downloaded.
3. In Chrome or Edge, [open ReadIN with AI ready](https://beta.anqapdf.app/#ref=cze3sewgik). Click "Connect Zotero" at the top; when Chrome asks about your local network, click Allow. Safari on the Mac can't connect to Zotero (it doesn't let websites reach Zotero on your computer), so please use Chrome or Edge.

Then open a paper either way: right-click it in your library and choose "Open in ReadIN" (「ReadIN で開く」 in Japanese Zotero, 「在 ReadIN 中開啟」 in Traditional Chinese), or, if you're already reading it in Zotero, click "ReadIN" at the right of the toolbar. Web snapshots work too (plugin 0.7+): items with only a saved web page open in ReadIN as clean text with an outline; highlights and thoughts go into the item's "ReadIN 笔记" note. Renaming a paper in ReadIN (plugin 0.8+: the ✎ next to its title in Library › Papers) renames it in Zotero too. In mainland China, use the [China version](https://cn-beta.anqapdf.app/#invite=CN-T294-ZYYF-E8P6&from=zotero) (AI by DeepSeek) and [download the plugin here](https://cn-beta.anqapdf.app/yidu/readin-yidu.xpi).

**Contact**: Phoenix@anqalabs.org, or "Feedback" at the bottom left of ReadIN.

**Privacy**: the plugin makes no internet requests. It answers only ReadIN's own pages on your computer. Open source (AGPL-3.0), no obfuscation, no tracking.

> This plugin is not affiliated with or endorsed by Zotero. Zotero is a registered trademark of the Corporation for Digital Scholarship.

---

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
- Safari 不让 https 网页连 `http://127.0.0.1`（当成混合内容，请求根本发不出去；2026-11-24 在 Safari 27.2 上确认），所以 Safari 连不上，ReadIN 里请人换 Chrome 或 Edge。

## 许可证

AGPL-3.0。插件免费、开源；插件里没有任何密钥，也不做收费判断。
