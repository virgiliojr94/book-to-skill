# Security notice — malicious `book-to-skill` re-upload

**Date:** 2026-08-17

The only official `book-to-skill` repository is:

> **https://github.com/virgiliojr94/book-to-skill**

A separate repository at `Leutenegger/book-to-skill` is **not affiliated with, maintained by, or endorsed by this project**.

After being notified by the community, the maintainer of the official project independently reviewed the published source of that re-upload. The modified code contains behavior that is not present in the official project, including:

- disabling TLS certificate verification;
- sending host/system/repository metadata to an external Cloudflare Worker;
- enumerating local browser-extension storage associated with multiple cryptocurrency wallets and Ledger application data;
- archiving and uploading collected local data to an external endpoint on macOS;
- shipping a Windows ZIP/EXE payload that the modified CLI can automatically extract and launch.

## Do not install or run the re-upload

If you installed or executed `Leutenegger/book-to-skill`, do not run it again.

Users who executed it on a system containing affected wallet software should treat the relevant local wallet data as potentially compromised and follow the wallet provider's incident-recovery guidance from a clean device.

## Verify before installing

Use only the official repository and installation source:

```bash
npx skills add virgiliojr94/book-to-skill
```

or:

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git
```

The official project does not contain the wallet-enumeration or exfiltration behavior described above.

## Evidence and tracking

Community report and maintainer confirmation:

- https://github.com/virgiliojr94/book-to-skill/issues/174

The malicious re-upload has been reported to the relevant service providers.
