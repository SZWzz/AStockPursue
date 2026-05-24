# Security Policy

## Supported Versions

| Version | Supported |
|---------|:---------:|
| latest  | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue.**
2. Contact the maintainers directly via email or private channel.
3. Include steps to reproduce, potential impact, and any suggested fixes.

We will acknowledge your report within **5 business days**.

## Security Design

- **Authentication** — JWT-based, passwords SHA256 hashed with random salt
- **Credentials** — AES-256-GCM encrypted at rest (DB password, LLM keys, data source tokens)
- **Sandbox Execution** — Indicator code runs in isolated sandbox with import whitelist, timeout, and subprocess isolation
- **API Access** — All endpoints require valid JWT token, no unauthenticated access

## Disclosure

- Do not publicly disclose vulnerabilities until a fix is released.
- Reporters will be credited in release notes (unless anonymity is preferred).
