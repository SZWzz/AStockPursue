import { describe, it, expect, beforeEach } from "vitest";

// We test the authHeaders and withAuthQuery helpers in isolation
const authHeadersModule = await import("@/lib/apiAuth");

describe("authHeaders", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns empty object when no token is stored", () => {
    const headers = authHeadersModule.authHeaders();
    expect(headers).toEqual({});
  });

  it("returns Authorization header when token is stored", () => {
    localStorage.setItem("vt_token", "test-jwt-token");
    const headers = authHeadersModule.authHeaders();
    expect(headers).toEqual({ Authorization: "Bearer test-jwt-token" });
  });
});

describe("withAuthQuery", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns URL unchanged when no token", () => {
    const url = authHeadersModule.withAuthQuery("/api/test");
    expect(url).toBe("/api/test");
  });

  it("appends jwt query param when token exists", () => {
    localStorage.setItem("vt_token", "my-token");
    const url = authHeadersModule.withAuthQuery("/api/test");
    expect(url).toBe("/api/test?jwt=my-token");
  });

  it("appends with & when URL already has query params", () => {
    localStorage.setItem("vt_token", "my-token");
    const url = authHeadersModule.withAuthQuery("/api/test?foo=bar");
    expect(url).toBe("/api/test?foo=bar&jwt=my-token");
  });
});
