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

### Authentication & Authorization

- **JWT Authentication** — Token-based with persistent `JWT_SECRET`, supports Authorization header and `?jwt=` query parameter (for SSE EventSource). `API_AUTH_KEY` fallback for MCP/CLI access.
- **Password Hashing** — PBKDF2-HMAC-SHA256 with 600,000 iterations and random salt. Backward-compatible with legacy SHA256 hashes.
- **Role-Based Access** — Admin-only endpoints (user management, MCP settings) enforce `role === "admin"` check. Regular users cannot access other users' data.
- **Per-User Isolation** — LLM config, data source tokens, skill config, sessions, and paper trading runs are all scoped to `user_id`. Imported skills stored in `~/.AStockPursue/skills/{user_id}/`.

### Credential Protection

- **Encryption at Rest** — AES-256-GCM encrypted storage for: DB password, LLM API keys, data source tokens (Tushare/OKX/Twelve Data/Finnhub/Tiingo). Encryption key stored separately.
- **Environment Injection** — Tokens loaded from DB → `os.environ` via `require_auth` middleware at request time. Never persisted to `.env` file for multi-user deployments.
- **Placeholder Detection** — Empty/placeholder tokens (`"your-tushare-token"`) are detected and treated as unconfigured, preventing accidental SDK initialization with invalid credentials.

### Sandbox Execution

- **Import Whitelist** — Only `numpy`, `pandas`, `math`, `json`, `datetime`, `collections`, `functools`, `itertools`, `statistics`, `decimal`, `fractions`, `operator`, `copy`, `typing`, `re`, `warnings`, `dataclasses`, `enum`, `abc`, `scipy`, `sklearn` are importable. All other imports blocked.
- **Safe `__builtins__`** — Custom `build_safe_builtins()` restricts builtins to ~60 whitelisted functions. `__import__` replaced with safe import gate. `__build_class__` preserved for class definitions. Dangerous functions (`eval`, `exec`, `compile`, `open`, `getattr`, `setattr`) removed.
- **Safe `sys` Injection** — Read-only `sys` object with `maxsize`, `float_info`, `version_info`, `version`, `platform`, `byteorder`. No `sys.exit()`, `sys.path`, or `sys.modules`.
- **AST + Regex Double Validation** — `validate_code_safety()` checks code against 50+ dangerous patterns (os.system, subprocess, eval, importlib, etc.) before execution, plus AST tree inspection for dangerous imports and calls.
- **Timeout Protection** — 30-second execution timeout via `signal.SIGALRM` (Unix) or `threading.Timer` (cross-platform). Resource limits via `setrlimit` when `SAFE_EXEC_ENABLE_RLIMIT=true`.
- **Process Isolation** — `safe_exec_isolated()` runs code in a `multiprocessing.Process` (spawn mode), providing full memory isolation for untrusted code.

### API Security

- **Centralized Auth Middleware** — `require_auth` dependency applied to all API routes and sub-routers. Automatically loads per-user data source tokens.
- **Code Safety on Save** — All `/save` endpoints (Indicator Lab, Strategy Lab) run `validate_code_safety()` before persisting user code.
- **Path Traversal Prevention** — `PATH_SAFETY.validate()` checks all file paths against allowed roots (`ASTOCKPURSUE_ALLOWED_RUN_ROOTS`). Prevents arbitrary filesystem access.
- **Upload Security** — File upload endpoints validate content types and filenames. Skill ZIP import validates `SKILL.md` frontmatter before extraction.
- **SPA Route Fallback** — `SPAStaticFiles` serves `index.html` only for paths not matching any API route, preventing information disclosure.

### Data Integrity

- **Atomic File Writes** — `mkstemp` + `os.replace` for indicator/strategy repository writes. `fcntl.flock` (Unix) / `msvcrt.locking` (Windows) for JSONL append operations.
- **Pickle Cache Signing** — HMAC-SHA256 signatures on cached data. Tampered cache files are detected and regenerated.
- **JWT Secret Persistence** — `JWT_SECRET` stored in `.env` or `runtime_root/.jwt_secret`, preventing key rotation across restarts/workers.

### Deployment

- **Docker Isolation** — Application runs in container with minimal privileges.
- **Database** — PostgreSQL with encrypted credentials. Connection pooling with configurable min/max.
- **MCP Server** — Shell tools (`write_file`, `read_file`, `web_search`) disabled by default in SSE transport mode. Only stdio mode has full tool access.

## Disclosure

- Do not publicly disclose vulnerabilities until a fix is released.
- Reporters will be credited in release notes (unless anonymity is preferred).
