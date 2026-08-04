# Contributing to book-to-skill

Thanks for helping improve book-to-skill. This project turns books and documents
into structured agent skills; contributions that make extraction more robust,
generation higher-signal, or the docs clearer are all welcome.

## Ground rules

- **Measure, don't assert.** A change that claims a gain should show it — a test,
  a benchmark number from `tools/discovery_tax.py`, or a before/after. PRs that add
  weight (e.g. to `SKILL.md`, which is loaded on every run) without a demonstrated
  benefit will be asked for evidence first.
- **Keep `SKILL.md` lean.** It is the always-loaded converter spec. Prefer editing
  existing steps over adding new ones; justify net additions.
- **Never ship raw book text.** Generated skills synthesize; they never reproduce
  long passages. Respect source licenses (see the README's Copyright section).

## Development

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git
cd book-to-skill
python3 -m venv .venv && . .venv/bin/activate
pip install pytest ruff
python3 scripts/extract.py --check     # see which optional extractors you have
```

Run the checks the CI runs before opening a PR:

```bash
ruff check .
pytest -q
python3 tools/validate_skill.py SKILL.md
```

## Pull requests

- One focused change per PR; small and reviewable.
- **Conventional Commits** for titles and commits: `feat:`, `fix:`, `docs:`,
  `chore:`, `test:`, `ci:` … (e.g. `fix(extractor): scan full text`).
- Add or update tests for any behavior change.
- **Do not edit `CHANGELOG.md`.** It is generated from Conventional Commit
  messages by [git-cliff](https://github.com/orhun/git-cliff) at release time.
  Your **PR title** must be a valid Conventional Commit (`fix:`, `feat:`,
  `docs:`, `perf:`, `refactor:`, `chore:`…) — squash-merge turns it into the
  commit, and that line becomes your changelog entry. CI checks the title.
- CI must be green (lint, test matrix py3.10–3.13, smoke, SKILL.md validation,
  PR title + description checks).
- **We don't accept PRs that add third-party or "related / built-with" project
  links to the README or docs.** Recognition in the README is a
  [GitHub Sponsors](https://github.com/sponsors/virgiliojr94) benefit (sponsors are
  listed in `BACKERS.md`). This keeps the project's most visible surface reserved
  for the people funding its upkeep. Building something inspired by book-to-skill
  is genuinely appreciated — sharing it in an issue or discussion is welcome.

## Releases

Maintainers cut releases with semantic versioning. The changelog is generated
from Conventional Commit messages — do not hand-edit it:

```bash
# 1. bump version in pyproject.toml
# 2. regenerate CHANGELOG.md from commits (needs git-cliff installed locally)
git-cliff --tag vX.Y.Z -o CHANGELOG.md
# 3. commit, tag, push
git commit -am "chore(release): vX.Y.Z"
git tag vX.Y.Z && git push origin master vX.Y.Z
# 4. publish a GitHub Release using the new CHANGELOG section as notes
```

git-cliff is a dev-only tool (a single static binary; not a runtime dependency
of book-to-skill). See `cliff.toml` for the type→section mapping.

## Reporting bugs / requesting features

Open an issue using the templates in `.github/ISSUE_TEMPLATE/`. For extraction
bugs, please include the format, page count, and whether `--check` shows the
relevant extractor installed.
