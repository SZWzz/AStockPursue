import { describe, it, expect } from "vitest";
import { PortType, isCompatible } from "@/workflow/types/workflow";

describe("PortType", () => {
  it("defines all expected port types", () => {
    expect(PortType.DF_OHLCV).toBe("df_ohlcv");
    expect(PortType.DF_FACTOR).toBe("df_factor");
    expect(PortType.SIGNAL).toBe("signal");
    expect(PortType.BACKTEST_RESULT).toBe("backtest_result");
    expect(PortType.ANY).toBe("any");
  });

  it("has unique values for all port types", () => {
    const values = Object.values(PortType);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });
});

describe("isCompatible", () => {
  it("returns true for same type", () => {
    expect(isCompatible(PortType.DF_FACTOR, PortType.DF_FACTOR)).toBe(true);
    expect(isCompatible(PortType.SIGNAL, PortType.SIGNAL)).toBe(true);
    expect(isCompatible(PortType.DF_OHLCV, PortType.DF_OHLCV)).toBe(true);
  });

  it("returns true when target is ANY (wildcard)", () => {
    expect(isCompatible(PortType.DF_FACTOR, PortType.ANY)).toBe(true);
    expect(isCompatible(PortType.BACKTEST_RESULT, PortType.ANY)).toBe(true);
    expect(isCompatible(PortType.SIGNAL, PortType.ANY)).toBe(true);
  });

  it("returns false for mismatched types", () => {
    expect(isCompatible(PortType.DF_FACTOR, PortType.SIGNAL)).toBe(false);
    expect(isCompatible(PortType.SIGNAL, PortType.BACKTEST_RESULT)).toBe(false);
    expect(isCompatible(PortType.DF_OHLCV, PortType.DF_FACTOR)).toBe(false);
  });

  it("returns false when source is ANY (ANY output → specific input not allowed)", () => {
    expect(isCompatible(PortType.ANY, PortType.DF_FACTOR)).toBe(false);
    expect(isCompatible(PortType.ANY, PortType.SIGNAL)).toBe(false);
  });

  it("handles all PortType values", () => {
    const allTypes = Object.values(PortType);
    for (const type of allTypes) {
      if (type !== PortType.ANY) {
        expect(isCompatible(type, type)).toBe(true);
        expect(isCompatible(type, PortType.ANY)).toBe(true);
      }
    }
  });
});
