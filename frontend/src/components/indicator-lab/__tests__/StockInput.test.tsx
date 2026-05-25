import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StockInput } from "@/components/indicator-lab/StockInput";

// Mock apiAuth
vi.mock("@/lib/apiAuth", () => ({
  authHeaders: () => ({}),
}));

describe("StockInput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with default placeholder", () => {
    render(<StockInput value="" onChange={() => {}} />);
    const input = screen.getByPlaceholderText("600519.SH");
    expect(input).toBeInTheDocument();
  });

  it("renders with custom placeholder", () => {
    render(<StockInput value="" onChange={() => {}} placeholder="Test placeholder" />);
    expect(screen.getByPlaceholderText("Test placeholder")).toBeInTheDocument();
  });

  it("displays current value in single mode", () => {
    render(<StockInput value="600519.SH" onChange={() => {}} />);
    expect(screen.getByText("600519.SH")).toBeInTheDocument();
  });

  it("displays chips in multi mode", () => {
    render(<StockInput value="AAPL.US, GOOGL.US" onChange={() => {}} multi />);
    expect(screen.getByText("AAPL.US")).toBeInTheDocument();
    expect(screen.getByText("GOOGL.US")).toBeInTheDocument();
  });

  it("calls onChange with typed code on Enter when no results", () => {
    const onChange = vi.fn();
    render(<StockInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("600519.SH");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });
    // onChange should be called with uppercase code
    expect(onChange).toHaveBeenCalledWith("AAPL");
  });

  it("removes value when X button clicked in single mode", () => {
    const onChange = vi.fn();
    render(<StockInput value="600519.SH" onChange={onChange} />);
    // Click the X button
    const xButton = screen.getByRole("button");
    fireEvent.click(xButton);
    expect(onChange).toHaveBeenCalledWith("");
  });
});
