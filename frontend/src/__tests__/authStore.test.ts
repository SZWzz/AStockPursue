import { describe, it, expect, beforeEach, vi } from "vitest";

// The auth store uses sessionStorage directly — mock it
const sessionStore: Record<string, string> = {};

let useAuthStore: any;

beforeEach(async () => {
  Object.keys(sessionStore).forEach((k) => delete sessionStore[k]);
  // Mock sessionStorage
  Object.defineProperty(window, "sessionStorage", {
    value: {
      getItem: (key: string) => sessionStore[key] ?? null,
      setItem: (key: string, value: string) => { sessionStore[key] = value; },
      removeItem: (key: string) => { delete sessionStore[key]; },
      clear: () => { Object.keys(sessionStore).forEach((k) => delete sessionStore[k]); },
      get length() { return Object.keys(sessionStore).length; },
      key: (index: number) => Object.keys(sessionStore)[index] ?? null,
    },
    writable: true,
  });
  // Reset Zustand store state between tests
  const mod = await import("@/stores/auth");
  useAuthStore = mod.useAuthStore;
  useAuthStore.setState({ token: null, user: null, loading: false });
});

describe("useAuthStore", () => {
  it("should initialise with no token and no user", () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(false);
  });

  it("should restore from sessionStorage on loadFromStorage", () => {
    sessionStore["vt_token"] = "test-jwt-token";
    sessionStore["vt_user"] = JSON.stringify({ user_id: 1, username: "testuser", role: "admin" });

    useAuthStore.getState().loadFromStorage();

    const state = useAuthStore.getState();
    expect(state.token).toBe("test-jwt-token");
    expect(state.user).toEqual({ user_id: 1, username: "testuser", role: "admin" });
  });

  it("should handle corrupted user JSON in sessionStorage", () => {
    sessionStore["vt_token"] = "test-jwt-token";
    sessionStore["vt_user"] = "not-valid-json";

    useAuthStore.getState().loadFromStorage();

    const state = useAuthStore.getState();
    // Should clear corrupted data
    expect(state.token).toBeNull();
    expect(sessionStore["vt_token"]).toBeUndefined();
  });

  it("should clear state on logout", () => {
    sessionStore["vt_token"] = "test-jwt-token";
    sessionStore["vt_user"] = JSON.stringify({ user_id: 1, username: "testuser", role: "admin" });

    useAuthStore.getState().loadFromStorage();
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(sessionStore["vt_token"]).toBeUndefined();
    expect(sessionStore["vt_user"]).toBeUndefined();
  });

  it("should set loading=true during login attempt", async () => {
    // Mock fetch to delay
    globalThis.fetch = vi.fn().mockImplementation(
      () => new Promise((resolve) =>
        setTimeout(() => resolve({ ok: false, json: () => Promise.resolve({ detail: "Invalid" }) }), 50)
      )
    );

    const loginPromise = useAuthStore.getState().login("user", "pass");
    expect(useAuthStore.getState().loading).toBe(true);

    await loginPromise;
    expect(useAuthStore.getState().loading).toBe(false);
  });

  it("should handle network errors in login", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

    const error = await useAuthStore.getState().login("user", "pass");
    expect(error).toBeTruthy();
    expect(useAuthStore.getState().loading).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("should return error message on registration failure", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Username already exists" }),
    });

    const error = await useAuthStore.getState().register("existinguser", "pass");
    expect(error).toBe("Username already exists");
    expect(useAuthStore.getState().loading).toBe(false);
  });
});
