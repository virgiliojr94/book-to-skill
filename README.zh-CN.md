<p align="center">
  <img src="docs/assets/banner.webp" alt="Booklin，book-to-skill 巫师，手持一本打开的书，书页化作星光并排列成有序网格" width="100%">
</p>

<h1 align="center">book-to-skill</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

> **翻译说明。** 以[英文 README](README.md) 为准。本翻译可能落后于 `master`。  
> 与英文版同步于 commit [`907be50`](https://github.com/virgiliojr94/book-to-skill/commit/907be508ee17428fea0179f9996bde80e5282a0f)（2026-08-31）。  
> 查看差异：`git log 907be50..master -- README.md`

<p align="center">
  <strong>将任意技术书籍、文档文件夹或资料集合，转换为统一的 Agent Skill——可在 GitHub Copilot CLI、Amp、Claude Code 或 Hermes Agent 中随时学习、查阅并在工作中使用。</strong>
</p>

<p align="center">
  <a href="https://github.com/virgiliojr94/book-to-skill/releases"><img src="https://img.shields.io/github/v/release/virgiliojr94/book-to-skill?style=for-the-badge&color=blueviolet" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/Agent_Skills-Open_Standard-blueviolet?style=for-the-badge" alt="Agent Skills standard">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Formats supported">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
  <a href="https://github.com/sponsors/virgiliojr94"><img src="https://img.shields.io/github/sponsors/virgiliojr94?style=for-the-badge&color=ea4aaa&logo=githubsponsors&logoColor=white" alt="Sponsor"></a>
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/27038?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-27038" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/27038" alt="virgiliojr94%2Fbook-to-skill | Trendshift" width="250" height="55"/></a>
  <a href="https://trendshift.io/repositories/27038?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-27038" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/27038/daily?language=Python" alt="virgiliojr94%2Fbook-to-skill | Trendshift (daily, Python)" width="250" height="55"/></a>
</p>

<p align="center">
  <a href="#-为什么">为什么</a> ·
  <a href="#-生成内容">生成内容</a> ·
  <a href="#-不止于书籍">不止于书籍</a> ·
  <a href="docs/how-it-works.md">工作原理</a> ·
  <a href="docs/usage.md">用法</a> ·
  <a href="docs/install.md">安装</a> ·
  <a href="docs/faq.md">FAQ</a> ·
  <a href="docs/performance.md">性能</a> ·
  <a href="docs/architecture.md">架构</a> ·
  <a href="CHANGELOG.md">更新日志</a>
</p>

<p align="center">
  <strong>回答一个问题时，比把整本书丢进上下文少消耗 24×–51× 的 token</strong>，基于真实书籍测量（<a href="docs/performance.md#the-discovery-loop-tax">测量方法</a>）。
</p>

**三步上手：**

1. **指定**文件、文件夹或 glob —— `/book-to-skill ./my-book.pdf`
2. **提炼**成 skill —— 框架、决策规则、反模式，以及按章节拆分的文件。提取的是结构，不是摘要。
3. **Agent 按需加载** —— 输入 `/my-book replication`，它会读取对应章节，基于真实内容回答，避免幻觉。

---

## 🤔 为什么

<img align="right" width="200" src="docs/assets/booklin.png" alt="Booklin — book-to-skill 吉祥物，紫色巫师手持一本书">

你买了一本很好的技术书，读了一遍。三个月后，你忘了第 7 章的存在。

常见的变通办法都不管用：
- 📄 「我搜一下 PDF」→ 得到的是页码列表，不是答案
- 🧠 「我问 Agent 这本书的内容」→ 要么幻觉，要么说没有内容
- 📝 「边读边做笔记」→ 最后得到一份 200 行的文档，再也不会打开

**book-to-skill 把书变成结构化 skill，Agent 按需加载。**

安装后，输入 `/your-book-slug replication`，Agent 会读取对应章节，基于实际内容回答。没有幻觉，不用翻 PDF。书成为你工作流的一部分。

兼容任何支持开放 [Agent Skills](https://github.com/agentskills/agentskills) 标准的宿主 —— GitHub Copilot CLI、Amp、Claude Code 和 Hermes Agent 都读取相同的 `SKILL.md` 格式。

---

## 📦 生成内容

运行 `/book-to-skill your-book.pdf`（或文件夹、glob、文件列表）后，会在 Agent 的 skills 目录下生成完整 skill（Copilot CLI：`~/.copilot/skills/<slug>/`；Amp 或跨 Agent：`~/.agents/skills/<slug>/`；Claude Code：`~/.claude/skills/<slug>/`；Hermes Agent：`$HERMES_HOME/skills/<category>/<slug>/`）：

| 文件 | 用途 | 大小 |
|------|------|------|
| `SKILL.md` | 核心心智模型 + 章节索引 | ~4,000 tokens |
| `chapters/ch01-*.md` … | 每章一个文件，按需加载 | ~1,000 tokens/章 |
| `glossary.md` | 关键术语，按字母排序并附章节引用 | ~1,500 tokens |
| `patterns.md` | 所有技巧、算法与设计模式 | ~2,000 tokens |
| `cheatsheet.md` | 决策表与快速参考规则 | ~1,000 tokens |

**章节文件按需加载** —— 在你问到相关主题之前，不会占用 skill 预算。

---

## 🏢 不止于书籍

名字里是「book」，但输入可以是任意结构化 prose。同一套提取流程适用于你拥有并反复查阅的知识：

- **内部文档** —— 架构决策记录、运行手册、入职指南。把整个 `docs/` 文件夹折叠成一个 skill，编码时随时提问。
- **品牌与设计系统** —— 语调指南、语气文档、组件原则。把品牌手册变成 skill，团队查询代替翻阅 60 页 PDF。
- **研究资料簇** —— 一叠论文加自己的笔记，合并为统一 skill，新资料到来时可更新（见[更新 / 折叠合并](#-用法)）。
- **规范与标准** —— RFC、API 合约、合规文档——常查但从没背下来。

如果你经常重新打开某份文档，希望自己已经背下来，它就是候选。

---

## 🧾 Discovery Loop Tax（发现循环税）

读 PDF 的 Agent 不只是读 —— 它还要*导航*：反复获取目录、回溯、每一轮重新处理。book-to-skill 在转换时**一次性**支付结构化成本，查询时 token 与答案规模成正比 —— 比把书丢进上下文**少 24×–51×**，基于真实书籍测量。

📊 **完整方法论、数据与逐书表格 → [docs/performance.md](docs/performance.md#the-discovery-loop-tax)**

---

## ⚙️ 工作原理

两部分：确定性的 Python **提取器**（文档 → 干净文本 + 元数据）和 spec 驱动的 **生成器**（Agent 按 `SKILL.md` 生成结构化 skill）。按需加载的章节文件保持已加载 skill 体积小巧。

🔧 **完整流程（Step 0–10、提取模式、token 预算）→ [docs/how-it-works.md](docs/how-it-works.md)**

---

## 🚀 用法

`/book-to-skill <path|folder|glob> [skill-name]` —— 另有仅分析、从分析结果生成、更新/折叠合并等模式。转换完成后，converter 可将 skill 发布到 GitHub（默认私有），任意宿主可通过 `npx skills add` 安装。

▶️ **所有模式与示例 → [docs/usage.md](docs/usage.md)**

💬 **实践案例 → [use cases](https://github.com/virgiliojr94/book-to-skill-use-cases)** —— 一本 DevEx 书变成 300+ 工程师调研；一本扫描 PDF 卡住后成为 [#130](https://github.com/virgiliojr94/book-to-skill/pull/130)。欢迎添加你的案例：账号在你自己的 Gist，索引只需一行 PR。

---

## 📥 安装

```bash
# 一条命令，任意宿主 —— 通过跨 Agent skills CLI：
npx skills add virgiliojr94/book-to-skill

# 或手动 —— 克隆到 skills 文件夹（注册 /book-to-skill）：
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# （Copilot CLI：~/.copilot/skills/ · Amp/跨 Agent：~/.agents/skills/）
# （Hermes Agent：${HERMES_HOME:-$HOME/.hermes}/skills/<category>/）
```

📥 **所有宿主、可选提取器与独立 CLI → [docs/install.md](docs/install.md)**

---

## ❓ FAQ

常见问题 —— 「为什么不直接把 PDF 丢进去？」、成本、隐私、非书籍输入、多文件书籍等。

❓ **答案 → [docs/faq.md](docs/faq.md)**

---

<details>
<summary>🔧 <strong>依赖要求</strong></summary>


提取器按格式依次尝试工具，使用第一个可用的。若均未安装，会提示应运行的安装命令。纯文本、Markdown、reStructuredText 和 AsciiDoc 无需额外依赖。

> **一条命令检查环境：** `python3 scripts/extract.py --check` 会打印每种格式已安装的提取器，以及缺失项的精确安装命令 —— 无需提供文件。

**PDF —— 按书籍类型选择：**

| 书籍类型 | 工具 | 安装 | 速度 |
|----------|------|------|------|
| 文字为主（散文，少表格） | `pdftotext` (poppler) | `sudo apt install poppler-utils` | ⚡ 即时 |
| 文字为主（备选） | `pypdf` | `pip3 install pypdf` | ⚡ 即时 |
| 文字为主（备选） | `pdfminer.six` | `pip3 install pdfminer.six` | ⚡ 即时 |
| **技术书（代码、表格、公式）** | **`docling`** | `pip3 install docling` | ~1.5s/页 |

> 提取开始前，skill 会询问书籍是**技术书**还是**文字为主**，并自动选择合适工具。Docling 保留 Markdown 表格与代码块；pdftotext 对纯散文更快。

> **扫描 PDF 需先 OCR。** 页面是图片、没有文字层的 PDF —— 拍照或扫描的书 —— 上述工具无法提取文字。提取器会检查前几页并立即停止并说明原因，而不是处理完整书籍后生成空 skill。请先自行 OCR，再转换结果：
>
> ```bash
> ocrmypdf input.pdf output.pdf
> ```

**EPUB：**

| 工具 | 安装 | 质量 |
|------|------|------|
| `ebooklib` + `beautifulsoup4` | `pip3 install ebooklib beautifulsoup4` | ⭐⭐⭐ 最佳 |
| 标准库 `zipfile` | 内置，无需安装 | ⭐⭐ 始终可用 |

**其他格式：**

| 格式 | 工具 | 安装 |
|------|------|------|
| DOCX | `python-docx`（备选：标准库 ZIP/XML） | `pip3 install python-docx` |
| HTML | `beautifulsoup4`（备选：标准库 `html.parser`） | `pip3 install beautifulsoup4` |
| RTF | `striprtf`（备选：正则） | `pip3 install striprtf` |
| MOBI / AZW / AZW3 | Calibre `ebook-convert`（外部应用，非 pip） | https://calibre-ebook.com/download |
| TXT / Markdown / reStructuredText / AsciiDoc | 内置 | — |

---


</details>

<details>
<summary>📁 <strong>仓库结构</strong></summary>


```
book-to-skill/
├── SKILL.md              # Skill 定义 + 逐步说明（生成器 spec）
├── scripts/
│   ├── extract.py        # 薄入口包装
│   └── extractor/        # 模块化提取包
│       ├── config.py     # 扩展名、路径、依赖常量
│       ├── dependencies.py  # 可选依赖探测 + --check
│       ├── exceptions.py # ExtractionError（单源失败，批处理安全）
│       ├── utils.py      # CLI 解析、多源解析、章节检测、runner
│       └── parsers/      # 各格式解析器（pdf、epub、docx、html、rtf、calibre、text）
├── tools/
│   ├── discovery_tax.py  # 测量 token 成本 vs 上下文 dump / discovery loop
│   └── validate_skill.py # 按宿主规则校验生成的 SKILL.md（--lens claude|copilot|amp）
├── tests/                # pytest 套件（提取、检测、discovery tax）
├── docs/
│   ├── performance.md    # 实测基准、discovery tax、成本
│   └── architecture.md   # 流水线 + 组件图
├── CHANGELOG.md          # 发布历史（semver）
├── CONTRIBUTING.md       # 开发环境、PR 规范、发布流程
├── SECURITY.md           # 漏洞报告
└── README.md             # 英文 README
```

---


</details>

---
## ⚖️ 版权与合理使用

book-to-skill **不包含任何书籍内容** —— 一页都没有。它是你指向已有文件的转换器。

- **本地处理。** 提取与分析在你的机器上运行。本工具不会上传你的文件。（若 Agent 的模型在云端运行，你喂给它的文本遵循该提供商的正常数据条款 —— 与任何 prompt 相同。）
- **使用你自己的副本。** 带上你购买的书、公司拥有的文档，或你有权阅读的论文。
- **输出是你的笔记。** 生成的 skill 是结构化、综合的衍生内容 —— 框架名、定义、要点 —— 不是原文再现。skill 明确从不复制原始段落（见 Quality Rule #7）。把它当作手写学习笔记：属于你，供个人使用。
- **不要重新分发。** 发布或分享受版权保护作品所生成的 skill 可能侵犯权利人权益。第三方书籍的 skill 请保持私有。内部文档、自己的写作和开放许可材料可在其许可证范围内分享。

如有疑问，请遵循源文档的许可证或条款。本项目是工具；如何使用由你负责。

---

## 💖 赞助

<img align="right" width="150" src="docs/assets/booklin-celebrating.png" alt="Booklin 庆祝">

book-to-skill 免费且 MIT 许可，由维护者在业余时间维护。若它为你节省了 token 或学习时间，欢迎赞助日常维护：PR 审查、多语言修复、发布与文档。

**[成为赞助者 → github.com/sponsors/virgiliojr94](https://github.com/sponsors/virgiliojr94)**

每位赞助者列在 [BACKERS.md](BACKERS.md)。感谢支持开放、隐私优先的工具。✨

## 许可证

MIT —— 适用于本仓库中的转换器（代码 + skill 定义），**不**适用于你用其处理的任何书籍或文档。

---

<!-- translation-meta: source=README.md@907be508ee17428fea0179f9996bde80e5282a0f date=2026-09-01 -->
<sub>简体中文翻译与英文 README 同步于 commit <code>907be50</code> · 英文版为准</sub>
