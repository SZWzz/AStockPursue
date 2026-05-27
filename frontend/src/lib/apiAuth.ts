const STORAGE = window.sessionStorage;

/** Max JWT length we accept in query params (SSE workaround). */
const MAX_JWT_LENGTH = 4096;

/** Pattern: base64url-encoded JWT (header.payload.signature). */
const JWT_PATTERN = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

export function authHeaders(): Record<string, string> {
  const jwt = STORAGE.getItem("vt_token");
  if (jwt) return { Authorization: `Bearer ${jwt}` };
  return {};
}

export function authQuerySuffix(): string {
  const jwt = STORAGE.getItem("vt_token");
  if (!jwt) return "";
  // Validate JWT shape before putting it in a query param (SSE workaround)
  if (jwt.length > MAX_JWT_LENGTH || !JWT_PATTERN.test(jwt)) {
    console.warn("authQuerySuffix: JWT failed validation — skipping query param");
    return "";
  }
  return `jwt=${encodeURIComponent(jwt)}`;
}

export function withAuthQuery(url: string): string {
  const suffix = authQuerySuffix();
  if (!suffix) return url;
  return `${url}${url.includes("?") ? "&" : "?"}${suffix}`;
}
