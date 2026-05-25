import { describe, it, expect } from "vitest";
import { ApiError, isAuthRequiredError, AUTH_REQUIRED_MESSAGE } from "@/lib/api";

describe("ApiError", () => {
  it("creates an error with status and name", () => {
    const err = new ApiError("Not Found", 404);
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not Found");
  });
});

describe("isAuthRequiredError", () => {
  it("returns true for 401 ApiError", () => {
    expect(isAuthRequiredError(new ApiError("unauthorized", 401))).toBe(true);
  });

  it("returns true for 403 ApiError", () => {
    expect(isAuthRequiredError(new ApiError("forbidden", 403))).toBe(true);
  });

  it("returns false for other ApiError statuses", () => {
    expect(isAuthRequiredError(new ApiError("not found", 404))).toBe(false);
    expect(isAuthRequiredError(new ApiError("server error", 500))).toBe(false);
  });

  it("returns false for non-ApiError", () => {
    expect(isAuthRequiredError(new Error("random"))).toBe(false);
    expect(isAuthRequiredError("string")).toBe(false);
  });
});

describe("AUTH_REQUIRED_MESSAGE", () => {
  it("is a non-empty string", () => {
    expect(typeof AUTH_REQUIRED_MESSAGE).toBe("string");
    expect(AUTH_REQUIRED_MESSAGE.length).toBeGreaterThan(0);
  });
});
