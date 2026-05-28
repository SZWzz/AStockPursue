import { describe, it, expect } from "vitest";

// Smoke tests for critical pure-logic functions
describe("paperTradingApi", () => {
  it("getSSEUrl includes BASE prefix", async () => {
    const { paperTradingApi } = await import("@/services/paperTrading");
    const url = paperTradingApi.getSSEUrl("test-run-123");
    expect(url).toContain("/v1/paper-trading/runs/test-run-123/stream");
  });
});
