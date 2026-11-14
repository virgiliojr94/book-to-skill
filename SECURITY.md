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

EPUB and DOCX archives are limited to 10,000 members, 32 MiB per expanded member,
and 128 MiB expanded in total. Only stored and deflated ZIP members are accepted.
Local archive reads, including ebooklib's member reads, also enforce a cumulative
128 MiB byte budget. An archive exceeding a limit is rejected as a failed source;
other sources in the batch can still be processed.
