export function authHeaders(): Record<string, string> {
  const jwt = window.localStorage.getItem("vt_token");
  if (jwt) return { Authorization: `Bearer ${jwt}` };
  return {};
}

export function authQuerySuffix(): string {
  const jwt = window.localStorage.getItem("vt_token");
  return jwt ? `jwt=${encodeURIComponent(jwt)}` : "";
}

export function withAuthQuery(url: string): string {
  const suffix = authQuerySuffix();
  if (!suffix) return url;
  return `${url}${url.includes("?") ? "&" : "?"}${suffix}`;
}
