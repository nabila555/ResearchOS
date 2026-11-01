# Security policy

ResearchOS handles private research documents, so security reports are taken seriously.

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x (latest `main`) | ✅ |
| older | ❌ |

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through
[GitHub Security Advisories](https://github.com/nabila555/ResearchOS/security/advisories/new).

Include:

- a description of the issue and its impact,
- steps to reproduce (a minimal file or request if possible),
- the affected version or commit.

Please do not include real private documents in a report. You can expect an acknowledgement
within 7 days. Once a fix is released, you will be credited unless you ask not to be.

## Security model

ResearchOS is designed as a **single-user application running on your own computer**:

- Both servers bind to `127.0.0.1` by default and have **no authentication**. Do not expose them to
  a network or the internet without putting authentication (for example a reverse proxy) in front.
- Uploaded files are validated by content, size-limited, stored under content hashes and confined
  to the data directory.
- URL import blocks private, loopback and link-local addresses, including after redirects.
- Model output is rendered as text or sanitised Markdown; raw HTML is never executed.
- API keys are read from the environment or local settings and are never returned by the API.
- Cloud AI (Claude API) is disabled unless both a key and explicit consent are present.

Issues of particular interest: path traversal, SSRF bypasses, script injection through documents
or model output, leakage of document content or keys, and malicious files that crash or hang
extraction.
