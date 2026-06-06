import { describe, it, expect, beforeEach } from "vitest";

// We test the authHeaders and withAuthQuery helpers in isolation
const authHeadersModule = await import("@/lib/apiAuth");

describe("authHeaders", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("returns empty object when no token is stored", () => {
    const headers = authHeadersModule.authHeaders();
    expect(headers).toEqual({});
  });

  it("returns Authorization header when token is stored", () => {
    window.sessionStorage.setItem("vt_token", "test-jwt-token");
    const headers = authHeadersModule.authHeaders();
    expect(headers).toEqual({ Authorization: "Bearer test-jwt-token" });
  });
});

describe("withAuthQuery", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("returns URL unchanged when no token", () => {
    const url = authHeadersModule.withAuthQuery("/api/test");
    expect(url).toBe("/api/test");
  });

  it("appends jwt query param when token exists", () => {
    window.sessionStorage.setItem("vt_token", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U");
    const url = authHeadersModule.withAuthQuery("/api/test");
    const expectedJwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
    expect(url).toBe("/api/test?jwt=" + encodeURIComponent(expectedJwt));
  });

  it("appends with & when URL already has query params", () => {
    window.sessionStorage.setItem("vt_token", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U");
    const url = authHeadersModule.withAuthQuery("/api/test?foo=bar");
    const expectedJwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
    expect(url).toBe("/api/test?foo=bar&jwt=" + encodeURIComponent(expectedJwt));
  });
});
