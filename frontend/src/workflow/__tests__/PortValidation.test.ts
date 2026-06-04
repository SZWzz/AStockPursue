/**
 * Tests for port-type compatibility logic (simplified flat enum).
 */
import { describe, it, expect } from "vitest";
import { isCompatible, PortType as PT } from "../types/workflow";

describe("isCompatible", () => {
  describe("exact match", () => {
    it("returns true for same type", () => {
      expect(isCompatible(PT.DF_OHLCV, PT.DF_OHLCV)).toBe(true);
    });
    it("returns false for different types", () => {
      expect(isCompatible(PT.DF_OHLCV, PT.DF_FACTOR)).toBe(false);
    });
  });

  describe("wildcard", () => {
    it("any target accepts everything", () => {
      expect(isCompatible(PT.DF_OHLCV, PT.ANY)).toBe(true);
      expect(isCompatible(PT.STOCK_LIST, PT.ANY)).toBe(true);
    });
  });

  describe("signal chain types", () => {
    it("signal → any is compatible", () => {
      expect(isCompatible(PT.SIGNAL, PT.ANY)).toBe(true);
    });
    it("backtest → attribution is NOT compatible", () => {
      expect(isCompatible(PT.BACKTEST_RESULT, PT.ATTRIBUTION)).toBe(false);
    });
    it("backtest → any is compatible", () => {
      expect(isCompatible(PT.BACKTEST_RESULT, PT.ANY)).toBe(true);
    });
  });
});
