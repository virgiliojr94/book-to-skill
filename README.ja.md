<p align="center">
  <img src="docs/assets/banner.webp" alt="book-to-skill の魔法使い Booklin が開いた本を持ち、そのページがきらめきとなって散らばり、整ったグリッドに収まっていく様子" width="100%">
</p>

<h1 align="center">book-to-skill</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.ja.md"><strong>日本語</strong></a>
</p>

<p align="center">
<strong>技術書、ドキュメントのフォルダー、資料の集まりを、ひとつにまとまったエージェントスキルに変えます。GitHub Copilot CLI、Amp、Claude Code、Codex、Hermes Agent、OpenCode、OpenClaw で作業しながら、学び、参照し、活用できます。</strong></p>

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
   <a href="https://www.star-history.com/virgiliojr94/book-to-skill"><img src="https://api.star-history.com/badge?repo=virgiliojr94/book-to-skill&type=rank" alt="Star History Rank" /></a>
</p>



<p align="center">
  <a href="#-なぜ必要か">なぜ必要か</a> ·
  <a href="#-生成されるもの">生成されるもの</a> ·
  <a href="#-本以外にも">本以外にも</a> ·
  <a href="docs/how-it-works.md">しくみ</a> ·
  <a href="docs/usage.md">使い方</a> ·
  <a href="docs/install.md">インストール</a> ·
  <a href="docs/faq.md">FAQ</a> ·
  <a href="docs/performance.md">パフォーマンス</a> ·
  <a href="docs/architecture.md">アーキテクチャ</a> ·
  <a href="CHANGELOG.md">変更履歴</a>
</p>

<p align="center">
  1 つの質問に答えるのに、<strong>本をまるごとコンテキストに入れる場合より 24～51 分の 1 のトークン</strong>で済みます。実際の本で測定しました（<a href="docs/performance.md#the-discovery-loop-tax">測定方法</a>）。
</p>

**3 ステップのしくみ：**

1. **指定する**：ファイル、フォルダー、glob を指定します — `/book-to-skill ./my-book.pdf`
2. **凝縮する**：本をスキルに凝縮します。フレームワーク、判断のルール、アンチパターン、章ごとのファイルです。要約ではなく、構造です。
3. **エージェントが必要なときに読み込む**：`/my-book replication` と聞くと、適切な章を読み、実際の内容から答えます。ハルシネーションはありません。

---

## 🤔 なぜ必要か

<img align="right" width="200" src="docs/assets/booklin.png" alt="Booklin — 本を持った紫色の魔法使いの、book-to-skill のマスコット">

すばらしい技術書を買って、一度読みます。3 か月後には、第 7 章があったことさえ思い出せません。

よくある回避策は役に立ちません。
- 📄「PDF を検索すればいい」→ 返ってくるのはページの一覧で、答えではありません
- 🧠「エージェントにこの本のことを聞こう」→ ハルシネーションを起こすか、内容を持っていないと言われます
- 📝「読みながらメモを取ろう」→ 二度と開かない 200 行のドキュメントができあがります

**book-to-skill は、本をエージェントが必要なときに読み込む構造化されたスキルに変えることで、これを解決します。**

インストールしたら、`/your-book-slug replication` と入力するだけで、エージェントが適切な章を読み、実際の内容から答えます。ハルシネーションも、PDF をかき回す必要もありません。本がワークフローの一部になります。

オープンな [Agent Skills](https://github.com/agentskills/agentskills) 標準に対応したどのホストでも動きます。GitHub Copilot CLI、Amp、Claude Code、Codex、Hermes Agent、OpenCode、OpenClaw は、どれも同じ `SKILL.md` の形式を読みます。
---

## 📦 生成されるもの

`/book-to-skill your-book.pdf`（またはフォルダー、glob、ファイルの一覧）を実行すると、ユーザー単位のエージェント共通のスキルディレクトリ `~/.agents/skills/<slug>/` に完全なスキルが作られます。これは、Copilot CLI、Amp、Codex、OpenCode、OpenClaw がそのまま見つけられる 1 つのコピーです（OpenCode は独自の管理ルート `~/.config/opencode/skills/<slug>/` も読みます。OpenClaw はデフォルトの状態ディレクトリを使っている場合にもこれを見つけます。デフォルトでない `OPENCLAW_STATE_DIR` を使っている場合は、代わりに有効な状態の `skills/` ルートを使ってください）。Claude Code の下で実行した場合、コンバーターは `~/.claude/skills/<slug>/` に検証付きのシンボリックリンクも作ろうとします。リンクを読み戻して確認できれば Claude Code からスキルが見え、できなければ実行のレポートにそう表示されます。Hermes Agent は個人のスキルをカテゴリーごとに分けていて、エージェント共通のルートを探さないので、Hermes へのインストールは代わりに `/skills/<category>/<slug>/` に置かれます。OpenClaw の管理先、OpenCode の管理先、プロジェクトのローカルの配置先は、明示的に指定すれば引き続き使えます。

| ファイル | 目的 | サイズ |
|------|---------|------|
| `SKILL.md` | 中心となるメンタルモデル + 章の索引 | 約 4,000 トークン |
| `chapters/ch01-*.md` … | 章ごとに 1 ファイル、必要なときに読み込み | それぞれ約 1,000 トークン |
| `glossary.md` | すべての重要な用語を、章の参照付きでアルファベット順に並べたもの | 約 1,500 トークン |
| `patterns.md` | すべてのテクニック、アルゴリズム、デザインパターン | 約 2,000 トークン |
| `cheatsheet.md` | 判断の表と、すぐに参照できるルール | 約 1,000 トークン |

**章のファイルは必要なときに読み込まれます**。そのトピックについて質問するまで、スキルの予算には数えられません。

---

## 🏢 本以外にも

名前は「book」ですが、入力には構造のある文章なら何でも使えます。同じ抽出が、あなたが持っていて何度も読み返す知識にも使えます。

- **社内のドキュメント**：アーキテクチャの意思決定の記録、ランブック、オンボーディングのガイド。`docs/` フォルダー全体を 1 つのスキルにまとめ、コードを書きながら質問できます。
- **ブランドとデザインシステム**：ボイスのガイドライン、トーン・オブ・ボイスのドキュメント、コンポーネントの原則。60 ページの PDF を流し読みする代わりに、ブランドブックをチームで問い合わせられるスキルに変えられます。
- **研究の集まり**：論文の束と自分のメモを 1 つのまとまったスキルに統合し、新しい資料が入るたびに更新できます（[Update / fold-in](#-使い方) をご覧ください）。
- **仕様と標準**：参照はしても覚えはしない RFC、API の契約、コンプライアンスのドキュメント。

覚えておけたらよかったのにと思うほど何度も開くドキュメントがあれば、それが候補です。

---


## 🧾 探索ループの税

PDF を読むエージェントは、ただ読むだけではなく *ナビゲート* します。目次を取り直し、引き返し、ターンのたびにそのすべてを処理し直すのです。book-to-skill は、その構造化のコストを変換のときに **1 回だけ** 払うので、問い合わせのコストは答えに見合ったものに収まります。本をまるごとコンテキストに入れる場合より **24～51 分の 1 のトークン** で済み、実際の本で測定しました。

📊 **すべての方法論、数字、本ごとの表 → [docs/performance.md](docs/performance.md#the-discovery-loop-tax)**

---

## ⚙️ しくみ

2 つの部分からなります。決定論的な Python の **抽出器**（ドキュメント → きれいなテキスト + メタデータ）と、仕様にもとづく **生成器**（エージェントが `SKILL.md` に従って、それを構造化されたスキルに変えます）です。必要なときに読み込む章のファイルが、読み込むスキルを小さく保ちます。

🔧 **すべての手順（Steps 0–10、抽出のモード、トークンの予算）→ [docs/how-it-works.md](docs/how-it-works.md)**

---

## 🚀 使い方

`/book-to-skill <path|folder|glob> [skill-name]` に加えて、分析だけ、分析からの生成、更新 / 取り込みのモードがあります。変換の後、コンバーターはスキルを GitHub に公開できる（デフォルトは非公開）ので、どのホストでも `npx skills add` でインストールできます。

▶️ **すべてのモードと例 → [docs/usage.md](docs/usage.md)**

💬 **実際の使われ方 → [use cases](https://github.com/virgiliojr94/book-to-skill-use-cases)**：DevEx の本は 300 人以上のエンジニアへの調査になり、止まってしまったスキャン PDF は [#130](https://github.com/virgiliojr94/book-to-skill/pull/130) になりました。あなたの事例も追加してください。記録はあなた自身の Gist に置き、索引には 1 行の PR を送るだけです。

---

## 📥 インストール

```bash
# One command, any host — via the cross-agent skills CLI:
npx skills add virgiliojr94/book-to-skill

# Or manually — clone into your skills folder (registers /book-to-skill):
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# (Copilot CLI: ~/.copilot/skills/ · Amp/cross-agent: ~/.agents/skills/)
# (Hermes Agent: ${HERMES_HOME:-$HOME/.hermes}/skills/<category>/)
# (OpenClaw: ${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/skills/; ~/.agents/skills/ only with default state)
# (OpenCode: ~/.agents/skills/ — it also reads ~/.config/opencode/skills/)
```

📥 **すべてのホスト、任意の抽出器、単独で使える CLI → [docs/install.md](docs/install.md)**

---

## ❓ FAQ

よくある質問：「PDF をまるごと入れればいいのでは？」、コスト、プライバシー、本以外の入力、複数のファイルからなる本。

❓ **回答 → [docs/faq.md](docs/faq.md)**

---

<details>
<summary>🔧 <strong>必要なもの</strong></summary>


抽出器は、形式ごとに順番にツールを試し、最初に使えるものを使います。何もインストールされていなければ、実行すべきコマンドを教えてくれます。プレーンテキスト、Markdown、reStructuredText、AsciiDoc には追加の依存関係は必要ありません。

> **1 つのコマンドで環境を確認できます：** `python3 scripts/extract.py --check` は、すべての形式についてどの抽出器がインストールされているかと、足りないものをインストールする正確なコマンドを表示します。ファイルは必要ありません。

**PDF — 本の種類で選びます：**

| 本の種類 | ツール | インストール | 速度 |
|-----------|------|---------|-------|
| 文章中心（散文、表が少ない） | `pdftotext` (poppler) | `sudo apt install poppler-utils` | ⚡ 一瞬 |
| 文章中心の代替 | `pypdf` | `pip3 install pypdf` | ⚡ 一瞬 |
| 文章中心の代替 | `pdfminer.six` | `pip3 install pdfminer.six` | ⚡ 一瞬 |
| **技術書（コード、表、数式）** | **`docling`** | `pip3 install docling` | 1 ページあたり約 1.5 秒 |

> 抽出を始める前に、スキルは本が **技術書** か **文章中心** かを尋ね、適切なツールを自動で選びます。Docling は Markdown の表とコードブロックを保ちます。散文だけの本には pdftotext のほうが速いです。

> **スキャンした PDF には、まず OCR が必要です。** ページが画像でテキストの層がない PDF（撮影した本やスキャンした本）からは、これらのツールでは何も抽出できません。抽出器は最初の数ページを確認し、本全体を処理して空のスキルを作るのではなく、説明を付けてすぐに止まります。自分で OCR を実行してから、その結果を変換してください。
>
> ```bash
> ocrmypdf input.pdf output.pdf
> ```

**EPUB：**

| ツール | インストール | 品質 |
|------|---------|---------|
| `ebooklib` + `beautifulsoup4` | `pip3 install ebooklib beautifulsoup4` | ⭐⭐⭐ 最良 |
| 標準ライブラリの `zipfile` | 組み込み — インストール不要 | ⭐⭐ 常に使える |

**そのほかの形式：**

| 形式 | ツール | インストール |
|--------|------|---------|
| DOCX | `python-docx`（代替：標準ライブラリの ZIP/XML） | `pip3 install python-docx` |
| HTML | `beautifulsoup4`（代替：標準ライブラリの `html.parser`） | `pip3 install beautifulsoup4` |
| RTF | `striprtf`（代替：正規表現） | `pip3 install striprtf` |
| MOBI / AZW / AZW3 | Calibre の `ebook-convert`（pip ではなく外部のアプリ） | https://calibre-ebook.com/download |
| TXT / Markdown / reStructuredText / AsciiDoc | 組み込み | — |

---


</details>

<details>
<summary>📁 <strong>リポジトリの構成</strong></summary>


```
book-to-skill/
├── SKILL.md              # Skill definition + step-by-step instructions (the generator spec)
├── scripts/
│   ├── extract.py        # Thin entrypoint wrapper
│   └── extractor/        # Modular extraction package
│       ├── config.py     # Extensions, paths, dependency constants
│       ├── dependencies.py  # optional-dep probing + --check
│       ├── exceptions.py # ExtractionError (per-source failures, batch-safe)
│       ├── utils.py      # CLI parsing, multi-source resolution, chapter detection, runner
│       └── parsers/      # Format-specific parsers (pdf, epub, docx, html, rtf, calibre, text)
├── tools/
│   ├── discovery_tax.py  # measures token cost vs context-dump / discovery loop
│   └── validate_skill.py # checks a generated SKILL.md against host rules (--lens claude|copilot|amp|hermes|openclaw|opencode)
├── tests/                # pytest suite (extraction, detection, discovery tax)
├── docs/
│   ├── performance.md    # measured benchmarks, discovery tax, cost
│   └── architecture.md   # pipeline + component map
├── CHANGELOG.md          # release history (semver)
├── CONTRIBUTING.md       # dev setup, PR conventions, release process
├── SECURITY.md           # vulnerability reporting
└── README.md             # This file
```

---


</details>

---
## ⚖️ 著作権とフェアユース

book-to-skill には **本の内容は一切含まれていません**。1 ページもです。これは、すでに持っているファイルを指定して使うコンバーターです。

- **処理はローカルです。** 抽出と分析はあなたのマシンで行われます。このツールがあなたのファイルをアップロードすることはありません。（エージェントのモデルがクラウドで動いている場合、渡したテキストは、ほかのプロンプトと同じく、そのプロバイダーの通常のデータの規約に従います。）
- **自分のコピーを使います。** 買った本、会社が所有するドキュメント、読む権利を持っている論文を使ってください。
- **出力はあなたのメモです。** 生成されたスキルは、構造化して統合した派生物（フレームワークの名前、定義、要点）であり、本文の複製ではありません。スキルは原文の一節をそのまま写すことを明示的に禁じています（Quality Rule #7 をご覧ください）。手書きの勉強ノートのように、個人で使うあなたのものとして扱ってください。
- **再配布しないでください。** 著作権のある作品から生成したスキルを公開したり共有したりすると、権利者の権利を侵害するおそれがあります。第三者の本のスキルは非公開にしてください。社内のドキュメント、自分の書いたもの、オープンなライセンスの資料は、そのライセンスの範囲内で共有してかまいません。

迷ったときは、元のドキュメントのライセンスや規約に従ってください。このプロジェクトはツールであり、どう使うかはあなた次第です。

---

## 💖 スポンサー

<img align="right" width="150" src="docs/assets/booklin-celebrating.png" alt="お祝いする Booklin">

book-to-skill は無料で MIT ライセンスであり、個人の時間で保守されています。トークンや勉強の時間を節約できたなら、PR のレビュー、多言語の修正、リリース、ドキュメントといった保守のためのスポンサーをご検討ください。

**[スポンサーになる → github.com/sponsors/virgiliojr94](https://github.com/sponsors/virgiliojr94)**

すべてのスポンサーは [BACKERS.md](BACKERS.md) に掲載されています。オープンでプライバシーを第一にしたツールを支えてくださり、ありがとうございます。✨

## ライセンス

MIT — このリポジトリのコンバーター（コード + スキルの定義）に適用されるもので、これで処理する本やドキュメントには **適用されません**。

<!-- translation-meta: source=README.md@e7bb659d3261491c8b28793dcb9102fa64a46c22 date=2026-11-07 scope=destination-policy -->
