<h1 align="center">book-to-skill for Codex</h1>

<p align="center">
  <strong>把技术书、文档和电子书转换成可复用的 Codex Skill。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-Skill-black?style=for-the-badge" alt="Codex Skill">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Supported formats: PDF, EPUB, DOCX, Markdown, HTML, RTF, MOBI">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  <a href="#中文">中文</a> ·
  <a href="#english">English</a>
</p>

---

<details open id="中文">
<summary><strong>中文</strong></summary>

## 这是什么

`book-to-skill` 可以把一本 PDF、EPUB、DOCX、Markdown、HTML、RTF 或 MOBI/AZW/AZW3 文档转换成结构化的 Codex Skill。它不是简单生成读书笔记，而是从书里抽取框架、心智模型、原则、方法、反模式和章节索引，让 Codex 以后可以按需读取相关章节并基于原文内容回答。

生成后的 skill 默认放在：

```text
~/.codex/skills/<skill-name>/
```

## 为什么需要它

你读过一本很好的技术书，几个月后却想不起第 7 章讲了什么。常见办法都不太理想：

- 搜 PDF：得到的是页面列表，不是可执行的答案。
- 直接问模型：模型可能不知道这本书，或者把训练数据里的二手印象说成事实。
- 自己做笔记：最后往往变成一份很长、很少再打开的文档。

`book-to-skill` 的做法是先把书编译成 skill。之后你可以用自然语言问 Codex，例如：

```text
Use the designing-data-intensive-apps skill to explain replication.
```

Codex 会根据 skill 里的主题索引读取对应章节，而不是每次把整本书塞进上下文。

## 会生成什么

运行后会创建一个完整 skill：

| 文件 | 作用 | 典型大小 |
|------|------|----------|
| `SKILL.md` | 核心心智模型、章节索引、主题索引 | 约 4,000 tokens |
| `chapters/ch01-*.md` 等 | 每章一个文件，按需读取 | 每章约 1,000 tokens |
| `glossary.md` | 关键术语表，按字母排序并标注章节 | 约 1,500 tokens |
| `patterns.md` | 技术、算法、设计模式和方法 | 约 2,000 tokens |
| `cheatsheet.md` | 决策表、对照表和快速参考 | 约 1,000 tokens |

章节文件是按需加载的；只有当你问到相关主题或章节时，Codex 才需要读取它们。

## 安装

让 Codex 从这个 fork 安装：

```text
Install the book-to-skill skill from https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md
```

也可以手动安装：

```bash
mkdir -p ~/.codex/skills/book-to-skill/scripts

curl -L -o ~/.codex/skills/book-to-skill/SKILL.md \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md

curl -L -o ~/.codex/skills/book-to-skill/scripts/extract.py \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/scripts/extract.py
```

如果你想直接测试当前适配分支，可以把 URL 中的 `master` 换成 `codex/codex-skill-adapter`。

## 使用方式

在 Codex 里用自然语言调用：

```text
Use the book-to-skill skill to convert ~/Downloads/designing-data-intensive-applications.pdf into a Codex skill.

Use the book-to-skill skill to convert ~/books/clean-code.epub into a Codex skill named clean-code.

Use the book-to-skill skill to convert /tmp/ddd-evans.pdf into a Codex skill named domain-driven-design.
```

生成后可以这样使用书本 skill：

```text
Use the designing-data-intensive-apps skill to load the book's core mental models.
Use the designing-data-intensive-apps skill to explain replication.
Use the designing-data-intensive-apps skill to dive into chapter 5.
Use the designing-data-intensive-apps skill to list the available chapters.
```

Claude Code 和 Amp 也可以通过各自兼容的 skill 目录使用这些生成文件；Codex 默认使用自然语言，不依赖 slash command。

## 支持格式和依赖

纯文本、Markdown、reStructuredText 和 AsciiDoc 不需要额外依赖。其他格式会按可用工具依次尝试：

| 格式 | 首选工具 | 备用方案 |
|------|----------|----------|
| PDF 文本型 | `pdftotext` | `PyPDF2`、`pdfminer.six` |
| PDF 技术型 | `docling` | PDF 文本抽取链 |
| EPUB | `ebooklib` + `beautifulsoup4` | 标准库 ZIP/HTML 解析 |
| DOCX | `python-docx` | 标准库 ZIP/XML 解析 |
| HTML | `beautifulsoup4` | 标准库 HTML parser |
| RTF | `striprtf` | 基础正则清理 |
| MOBI/AZW/AZW3 | Calibre `ebook-convert` | 无 |

Codex 适配版默认不会自动安装缺失依赖；只有在用户明确同意时才应执行安装命令。

## 工作流程

```text
PDF / EPUB / DOCX / 文本文档
        |
        v
选择 technical 或 text 抽取模式
        |
        v
scripts/extract.py
        |
        +-- full_text.txt
        +-- metadata.json
        |
        v
Codex 分析标题、作者、目录和章节结构
        |
        v
生成章节摘要、术语表、模式表、速查表和主 SKILL.md
        |
        v
~/.codex/skills/<skill-name>/
```

对于超过约 50K tokens 的书，skill 会建议用 `grep`、`sed`、章节偏移等方式按需读取，不一次性把整本书放进上下文。

## 本 fork 修改了什么

这个 fork 基于原项目做了 Codex 适配，主要修改包括：

- 把 README 和 `SKILL.md` 的默认目标从 Claude Code/Amp 调整为 Codex。
- 默认安装和生成路径改为 `~/.codex/skills`。
- 使用方式改为 Codex 自然语言触发，同时保留 Claude Code/Amp 兼容说明。
- `scripts/extract.py` 改为 `argparse` 参数解析。
- 新增 `--output-dir`，同时保留 `BOOK_SKILL_WORKDIR`。
- 缺失依赖默认不自动安装，减少意外修改本机环境的风险。
- 增加基于 Python 标准库 `unittest` 的轻量测试，不依赖 pytest。
- 保持 Python 3.9 兼容。
- README 改为中文优先的中英双语文档。

## 致谢

感谢原作者 [virgiliojr94](https://github.com/virgiliojr94) 创建并开源了 [book-to-skill](https://github.com/virgiliojr94/book-to-skill)。这个 fork 的核心思路、文档抽取流程和 skill 生成结构都来自原项目；本仓库主要是在此基础上做 Codex 使用体验、路径、安全默认值和文档层面的适配。

## 许可证

MIT。请保留原项目版权和许可证声明。

</details>

---

<details id="english">
<summary><strong>English</strong></summary>

## What This Is

`book-to-skill` turns a PDF, EPUB, DOCX, Markdown, HTML, RTF, or MOBI/AZW/AZW3 document into a structured Codex skill. It does not just write book notes. It extracts frameworks, mental models, principles, techniques, anti-patterns, chapter indexes, and topic indexes so Codex can later load the relevant chapter on demand and answer from the actual source.

Generated skills default to:

```text
~/.codex/skills/<skill-name>/
```

## Why

You read a great technical book, then three months later you cannot remember where chapter 7 covered that crucial idea. The usual workarounds are weak:

- Searching the PDF gives page hits, not applied answers.
- Asking a model directly can produce hallucinated or second-hand knowledge.
- Personal notes often become long documents you rarely reopen.

`book-to-skill` compiles the book into a skill first. Then you can ask Codex in natural language:

```text
Use the designing-data-intensive-apps skill to explain replication.
```

Codex reads the right chapter through the skill's topic index instead of loading the entire book into every conversation.

## What It Generates

Running the converter creates a complete skill:

| File | Purpose | Typical size |
|------|---------|--------------|
| `SKILL.md` | Core mental models, chapter index, topic index | ~4,000 tokens |
| `chapters/ch01-*.md` ... | One file per chapter, loaded on demand | ~1,000 tokens each |
| `glossary.md` | Key terms, alphabetized with chapter references | ~1,500 tokens |
| `patterns.md` | Techniques, algorithms, design patterns, methods | ~2,000 tokens |
| `cheatsheet.md` | Decision tables, comparison matrices, quick reference | ~1,000 tokens |

Chapter files are loaded on demand; Codex only reads them when the user asks about related topics or chapters.

## Install

Ask Codex to install from this fork:

```text
Install the book-to-skill skill from https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md
```

Or install manually:

```bash
mkdir -p ~/.codex/skills/book-to-skill/scripts

curl -L -o ~/.codex/skills/book-to-skill/SKILL.md \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md

curl -L -o ~/.codex/skills/book-to-skill/scripts/extract.py \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/scripts/extract.py
```

To test the current adapter branch directly, replace `master` with `codex/codex-skill-adapter` in the raw URLs.

## Usage

Use natural language in Codex:

```text
Use the book-to-skill skill to convert ~/Downloads/designing-data-intensive-applications.pdf into a Codex skill.

Use the book-to-skill skill to convert ~/books/clean-code.epub into a Codex skill named clean-code.

Use the book-to-skill skill to convert /tmp/ddd-evans.pdf into a Codex skill named domain-driven-design.
```

After generating a book skill, use it like this:

```text
Use the designing-data-intensive-apps skill to load the book's core mental models.
Use the designing-data-intensive-apps skill to explain replication.
Use the designing-data-intensive-apps skill to dive into chapter 5.
Use the designing-data-intensive-apps skill to list the available chapters.
```

Claude Code and Amp can still use the generated files through their compatible skill directories. Codex usage is natural-language-first and does not rely on slash commands.

## Formats and Dependencies

Plain text, Markdown, reStructuredText, and AsciiDoc need no extra dependencies. Other formats try the best available extractor first:

| Format | Preferred tool | Fallback |
|--------|----------------|----------|
| Text-heavy PDF | `pdftotext` | `PyPDF2`, `pdfminer.six` |
| Technical PDF | `docling` | PDF text extraction chain |
| EPUB | `ebooklib` + `beautifulsoup4` | stdlib ZIP/HTML parser |
| DOCX | `python-docx` | stdlib ZIP/XML parser |
| HTML | `beautifulsoup4` | stdlib HTML parser |
| RTF | `striprtf` | basic regex cleanup |
| MOBI/AZW/AZW3 | Calibre `ebook-convert` | none |

This Codex adapter does not auto-install missing dependencies by default. Dependency installation should only happen after the user explicitly approves it.

## How It Works

```text
PDF / EPUB / DOCX / text document
        |
        v
Choose technical or text extraction mode
        |
        v
scripts/extract.py
        |
        +-- full_text.txt
        +-- metadata.json
        |
        v
Codex analyzes title, author, ToC, and chapter structure
        |
        v
Generate chapter summaries, glossary, patterns, cheatsheet, and master SKILL.md
        |
        v
~/.codex/skills/<skill-name>/
```

For books over roughly 50K tokens, the skill encourages targeted access with `grep`, `sed`, and chapter offsets instead of loading the entire book into context.

## What Changed in This Fork

This fork adapts the original project for Codex:

- README and `SKILL.md` now default to Codex instead of Claude Code/Amp.
- Default install and generation path is `~/.codex/skills`.
- Usage is natural-language-first for Codex, while keeping Claude Code/Amp compatibility notes.
- `scripts/extract.py` now uses `argparse`.
- Added `--output-dir` while preserving `BOOK_SKILL_WORKDIR`.
- Missing dependencies are not auto-installed by default.
- Added lightweight standard-library `unittest` coverage without requiring pytest.
- Kept Python 3.9 compatibility.
- Reworked README into a Chinese-first bilingual document.

## Acknowledgements

Thanks to [virgiliojr94](https://github.com/virgiliojr94) for creating and open-sourcing [book-to-skill](https://github.com/virgiliojr94/book-to-skill). The core idea, extraction workflow, and generated skill structure come from the original project. This fork focuses on adapting the experience, paths, safer defaults, and documentation for Codex.

## License

MIT. Please keep the original copyright and license notice.

</details>

---

## Star History

<a href="https://www.star-history.com/?repos=JasonHe%2Fbook-to-skill&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&legend=top-left" />
 </picture>
</a>
