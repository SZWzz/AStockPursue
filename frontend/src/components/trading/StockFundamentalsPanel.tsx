import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/common/Skeleton";

interface Props {
  symbol: string;
  price: number;       // current price from chart
}

interface FinanceSnapshot {
  symbol: string;
  available: boolean;
  fields: Record<string, number | string>;
  field_count: number;
}

interface FinancialsData {
  symbol: string;
  income_statement: any[];
  balance_sheet: any[];
  cash_flow: any[];
  income_count: number;
  balance_count: number;
  cashflow_count: number;
}

interface ValuationData {
  symbol: string;
  price: number;
  eps_current: number;
  eps_forecast: number;
  pe_current: number;
  forward_pe: number;
  cagr: number;
  peg: number;
  pe_digestion_years: number;
  peg_signal: string;
  digestion_signal: string;
}

export function StockFundamentalsPanel({ symbol, price }: Props) {
  const [finance, setFinance] = useState<FinanceSnapshot | null>(null);
  const [financials, setFinancials] = useState<FinancialsData | null>(null);
  const [valuation, setValuation] = useState<ValuationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Valuation inputs
  const [epsCurrent, setEpsCurrent] = useState("");
  const [epsForecast, setEpsForecast] = useState("");
  const [targetPe, setTargetPe] = useState("30");

  // Load finance snapshot + financials on symbol change
  const loadData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError("");

    try {
      const [fin, fins] = await Promise.all([
        api.getStockFinance(symbol).catch(() => null),
        api.getStockFinancials(symbol).catch(() => null),
      ]);
      setFinance(fin);
      setFinancials(fins);

      // Pre-fill EPS from finance snapshot if available
      if (fin?.available && fin.fields) {
        const eps = fin.fields["eps"];
        if (eps && !epsCurrent) {
          setEpsCurrent(String(eps));
        }
      }
    } catch {
      setError("基本面数据加载失败");
    }
    setLoading(false);
  }, [symbol]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Compute valuation on demand
  const computeValuation = useCallback(async () => {
    if (!symbol || !epsCurrent || !epsForecast) return;
    try {
      const result = await api.getStockValuation(symbol, {
        price,
        eps_current: parseFloat(epsCurrent),
        eps_forecast: parseFloat(epsForecast),
        target_pe: targetPe ? parseFloat(targetPe) : undefined,
      }) as unknown as ValuationData;
      setValuation(result);
    } catch {
      setError("估值计算失败");
    }
  }, [symbol, price, epsCurrent, epsForecast, targetPe]);

  if (!symbol) {
    return <div className="text-center text-xs text-muted-foreground py-8">请先选择标的</div>;
  }

  if (loading) {
    return (
      <div className="p-3 space-y-2">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
    );
  }

  // Key fields from 37-field snapshot to highlight
  const keyFields = [
    { key: "eps", label: "EPS" },
    { key: "bvps", label: "每股净资产" },
    { key: "roe", label: "ROE%" },
    { key: "profit", label: "净利润(亿)", fmt: (v: number) => (v / 1e8).toFixed(2) },
    { key: "income", label: "营收(亿)", fmt: (v: number) => (v / 1e8).toFixed(2) },
    { key: "liutongguben", label: "流通股本(亿)", fmt: (v: number) => (v / 1e8).toFixed(2) },
    { key: "zongguben", label: "总股本(亿)", fmt: (v: number) => (v / 1e8).toFixed(2) },
    { key: "meigujingzichan", label: "每股净资产" },
    { key: "meigugongjijin", label: "每股公积金" },
    { key: "meiguweifeipeili", label: "每股未分配" },
  ];

  return (
    <div className="flex flex-col h-full overflow-auto p-3 gap-3 text-xs">
      {/* Error */}
      {error && (
        <div className="text-center text-red-500 text-xs py-2">{error}</div>
      )}

      {/* ── Finance Snapshot ─────────────────────────────────────── */}
      {finance?.available && (
        <section className="rounded-lg border bg-muted/10 p-2.5">
          <h3 className="text-[11px] font-semibold text-muted-foreground mb-2">
            财务快照 · {symbol}
          </h3>
          <div className="grid grid-cols-3 gap-1.5">
            {keyFields.map(({ key, label, fmt }) => {
              const raw = finance.fields[key];
              if (raw == null || raw === "") return null;
              const val = fmt ? fmt(Number(raw)) : (typeof raw === "number" ? raw.toFixed(2) : String(raw));
              return (
                <div key={key} className="text-center py-1">
                  <p className="text-[10px] text-muted-foreground">{label}</p>
                  <p className="font-mono font-semibold">{val}</p>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Valuation Calculator ─────────────────────────────────── */}
      <section className="rounded-lg border bg-muted/10 p-2.5">
        <h3 className="text-[11px] font-semibold text-muted-foreground mb-2">
          估值计算
        </h3>
        <div className="grid grid-cols-4 gap-1.5 mb-2">
          <div>
            <label className="text-[10px] text-muted-foreground">当前价</label>
            <input
              type="text"
              value={price.toFixed(2)}
              readOnly
              className="w-full rounded border px-1.5 py-0.5 text-[11px] font-mono bg-muted/30 text-muted-foreground"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground">EPS(TTM)</label>
            <input
              type="number"
              step="0.01"
              value={epsCurrent}
              onChange={(e) => setEpsCurrent(e.target.value)}
              className="w-full rounded border px-1.5 py-0.5 text-[11px] font-mono"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground">EPS(Fwd)</label>
            <input
              type="number"
              step="0.01"
              value={epsForecast}
              onChange={(e) => setEpsForecast(e.target.value)}
              className="w-full rounded border px-1.5 py-0.5 text-[11px] font-mono"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground">目标PE</label>
            <input
              type="number"
              step="0.1"
              value={targetPe}
              onChange={(e) => setTargetPe(e.target.value)}
              className="w-full rounded border px-1.5 py-0.5 text-[11px] font-mono"
            />
          </div>
        </div>
        <button
          onClick={computeValuation}
          disabled={!epsCurrent || !epsForecast}
          className="w-full rounded bg-primary text-primary-foreground text-[11px] py-1 font-medium disabled:opacity-50"
        >
          计算估值
        </button>

        {valuation && (
          <div className="grid grid-cols-3 gap-1.5 mt-2 pt-2 border-t">
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground">当期PE</p>
              <p className="font-mono font-bold">{valuation.pe_current === Infinity ? "∞" : valuation.pe_current}</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground">前向PE</p>
              <p className="font-mono font-bold">{valuation.forward_pe === Infinity ? "∞" : valuation.forward_pe}</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground">PEG</p>
              <p className={cn(
                "font-mono font-bold",
                valuation.peg_signal === "cheap" && "text-emerald-500",
                valuation.peg_signal === "expensive" && "text-red-500",
                valuation.peg_signal === "fair" && "text-amber-500",
              )}>
                {valuation.peg === Infinity ? "∞" : valuation.peg}
              </p>
            </div>
            <div className="text-center col-span-2">
              <p className="text-[10px] text-muted-foreground">PE消化时间</p>
              <p className="font-mono font-semibold">{valuation.pe_digestion_years === Infinity ? "∞" : `${valuation.pe_digestion_years} 年`}</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground">CAGR</p>
              <p className="font-mono font-semibold">{(valuation.cagr * 100).toFixed(1)}%</p>
            </div>
          </div>
        )}
      </section>

      {/* ── Financial Statements ──────────────────────────────────── */}
      {financials && financials.income_count > 0 && (
        <section className="rounded-lg border bg-muted/10 p-2.5">
          <h3 className="text-[11px] font-semibold text-muted-foreground mb-2">
            利润表（最近 {Math.min(3, financials.income_count)} 期）
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="text-left py-1">科目</th>
                  {financials.income_statement.slice(0, 3).map((item: any, i: number) => (
                    <th key={i} className="text-right py-1 px-1.5">{item["报告日"]?.slice(0, 7) || `P${i+1}`}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {["净利润", "营业总收入", "营业总成本", "营业利润"].map((key) => (
                  <tr key={key} className="border-t">
                    <td className="py-0.5">{key}</td>
                    {financials.income_statement.slice(0, 3).map((item: any, i: number) => (
                      <td key={i} className="text-right font-mono py-0.5 px-1.5">
                        {item[key] != null ? (Number(item[key]) / 1e8).toFixed(2) + "亿" : "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Balance Sheet ─────────────────────────────────────────── */}
      {financials && financials.balance_count > 0 && (
        <section className="rounded-lg border bg-muted/10 p-2.5">
          <h3 className="text-[11px] font-semibold text-muted-foreground mb-2">
            资产负债表（最近 {Math.min(3, financials.balance_count)} 期）
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="text-left py-1">科目</th>
                  {financials.balance_sheet.slice(0, 3).map((item: any, i: number) => (
                    <th key={i} className="text-right py-1 px-1.5">{item["报告日"]?.slice(0, 7) || `P${i+1}`}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {["资产总计", "负债合计", "股东权益合计"].map((key) => (
                  <tr key={key} className="border-t">
                    <td className="py-0.5">{key}</td>
                    {financials.balance_sheet.slice(0, 3).map((item: any, i: number) => (
                      <td key={i} className="text-right font-mono py-0.5 px-1.5">
                        {item[key] != null ? (Number(item[key]) / 1e8).toFixed(2) + "亿" : "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Not available */}
      {!finance?.available && !loading && (
        <div className="text-center text-xs text-muted-foreground py-4">
          暂无基本面数据（需要 mootdx 数据源）
        </div>
      )}
    </div>
  );
}
