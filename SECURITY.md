# Security Policy

## Scope

book-to-skill is a local conversion tool. It reads document files you point it at
and writes skill files to your skills directory. It does **not** upload your files,
phone home, or run a network service. The main security surface is:

- the Python extraction code (parsing untrusted document files), and
- the optional dependencies it can install on request (`pip install …` when you
  choose `--install-missing yes`).

## Supported versions

The latest released `1.x` version receives fixes. Please reproduce issues against
the most recent tag before reporting.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead use GitHub's
private vulnerability reporting:

- Go to the repository's **Security** tab → **Report a vulnerability**.

Include: affected version, a minimal reproduction (ideally a small sample file or
crafted input), and the impact you observed. We aim to acknowledge within a few days.

## Good practices for users

- Run `python3 scripts/extract.py --check` to see exactly which extractors are in
  use; install dependencies yourself if you prefer to control what is added.
- Only convert documents you trust and have the right to process (see the README's
  Copyright & fair-use section).

## Prompt-injection considerations

Source documents are untrusted input to the LLM-driven conversion pipeline. Generated
skills are auto-loaded in future sessions, so an injection that survives generation can
become persistent instruction in every later session. Review generated skill files before
first use, especially when converting documents from untrusted or public sources. The
built-in mitigations are the untrusted-content notice in [Step 2 of `SKILL.md`](SKILL.md#step-2--extract-text-from-the-source-documents)
and the advisory scan and review gate in [Step 9.5](SKILL.md#step-95--scan-the-generated-skill).
