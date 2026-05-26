import { useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, ChevronDown, ChevronRight, Code, Shield, Cpu } from "lucide-react";
import { useI18n } from "@/lib/i18n";

type SectionKey = "api" | "sandbox" | "config";

export function Docs() {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Record<SectionKey, boolean>>({
    api: true,
    sandbox: false,
    config: false,
  });

  const toggle = (key: SectionKey) => setExpanded((p) => ({ ...p, [key]: !p[key] }));

  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BookOpen className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">{t.docsTitle}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t.docsSubtitle}</p>
        </div>
      </div>

      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link to="/" className="hover:text-primary transition-colors">{t.home || "Home"}</Link>
        <span>/</span>
        <span className="text-foreground">{t.docsBreadcrumb}</span>
      </div>

      {/* ── Section 1: Strategy Writing API ── */}
      <Section
        icon={<Code className="h-5 w-5" />}
        title={t.docsApiTitle}
        expanded={expanded.api}
        onToggle={() => toggle("api")}
      >
        <SubSection title={t.docsApiContractTitle}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsApiContractDesc}</p>
          <CodeBlock language="python">{`class SignalEngine:
    def generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """
        Generate trading signals for multiple symbols.

        Args:
            data_map: dict keyed by symbol code (e.g. "600519.SH").
                      Each value is a pandas DataFrame with columns:
                      open, high, low, close, volume

                      Index is DatetimeIndex named "trade_date".

        Returns:
            signal_map: dict keyed by symbol code.
                        Each value is a pandas Series with the same
                        index as the input DataFrame.

                        Signal values: range [-1, 1]
                          1.0  = 100% long
                          0.5  = 50% long
                          0.0  = flat / no position
                         -0.5  = 50% short
                         -1.0  = 100% short
        """
        ...`}</CodeBlock>
        </SubSection>

        <SubSection title={t.docsApiDataFormat}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsApiDataFormatDesc}</p>
          <CodeBlock language="python">{`# data_map["000001.SZ"] example:
#            trade_date   open   high    low  close    volume
# 0  2024-01-02     10.50  10.80  10.30  10.65  12345678
# 1  2024-01-03     10.65  10.90  10.50  10.72  11234567
# ...

# Signal return example:
#            trade_date  signal
# 0  2024-01-02       0.0
# 1  2024-01-03       0.0
# ...
# 98  2024-05-20      0.0
# 99  2024-05-21      0.5   ← only the last bar carries the signal`}</CodeBlock>
        </SubSection>

        <SubSection title={t.docsApiExample}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsApiExampleDesc}</p>
          <CodeBlock language="python">{`import pandas as pd
import numpy as np
from typing import Dict

class SignalEngine:
    """Dual moving average crossover strategy."""

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signal_map: Dict[str, pd.Series] = {}

        for code, df in data_map.items():
            if len(df) < 60:
                continue

            # Compute fast and slow MAs
            fast_ma = df["close"].rolling(20).mean()
            slow_ma = df["close"].rolling(60).mean()

            signal = pd.Series(0.0, index=df.index)
            signal[fast_ma > slow_ma] = 1.0    # long when fast > slow
            signal[fast_ma < slow_ma] = -1.0   # short when fast < slow

            # Only the last bar's signal is used
            signal.iloc[:-1] = 0.0
            signal_map[code] = signal

        return signal_map`}</CodeBlock>
        </SubSection>

        <SubSection title={t.docsApiAvailableImports}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsApiAvailableImportsDesc}</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
            {["numpy", "pandas", "scipy", "sklearn", "math", "statistics",
              "datetime", "json", "collections", "functools", "itertools",
              "decimal", "fractions", "operator", "copy", "re",
              "typing", "dataclasses", "enum", "abc", "warnings"].map((m) => (
              <code key={m} className="px-2.5 py-1.5 rounded-md bg-muted/60 text-xs font-mono">{m}</code>
            ))}
          </div>
        </SubSection>

        <SubSection title={t.docsApiValidation}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsApiValidationDesc}</p>
          <ul className="list-disc pl-5 space-y-1.5 text-sm text-muted-foreground">
            <li>{t.docsApiValidationRequired1}</li>
            <li>{t.docsApiValidationRequired2}</li>
            <li>{t.docsApiValidationRequired3}</li>
          </ul>
        </SubSection>
      </Section>

      {/* ── Section 2: Sandbox Security ── */}
      <Section
        icon={<Shield className="h-5 w-5" />}
        title={t.docsSandboxTitle}
        expanded={expanded.sandbox}
        onToggle={() => toggle("sandbox")}
      >
        <SubSection title={t.docsSandboxOverview}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsSandboxOverviewDesc}</p>
        </SubSection>

        <SubSection title={t.docsSandboxForbidden}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsSandboxForbiddenDesc}</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm mb-4">
            {["os", "sys", "subprocess", "shutil", "signal", "ctypes",
              "socket", "requests", "urllib", "http", "smtplib",
              "pickle", "sqlite3", "pymysql", "psycopg2", "sqlalchemy",
              "multiprocessing", "threading", "asyncio", "concurrent",
              "importlib", "tempfile", "pathlib", "glob", "io"].map((m) => (
              <code key={m} className="px-2.5 py-1.5 rounded-md bg-danger/10 text-danger text-xs font-mono">{m}</code>
            ))}
          </div>
        </SubSection>

        <SubSection title={t.docsSandboxForbiddenFuncs}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsSandboxForbiddenFuncsDesc}</p>
          <div className="flex flex-wrap gap-2 text-sm">
            {["eval()", "exec()", "compile()", "open()", "getattr()", "setattr()",
              "globals()", "vars()", "dir()", "breakpoint()",
              "__import__()", "__class__", "__dict__", "__globals__",
              "__subclasses__", "__bases__", "__code__"].map((m) => (
              <code key={m} className="px-2.5 py-1.5 rounded-md bg-danger/10 text-danger text-xs font-mono">{m}</code>
            ))}
          </div>
        </SubSection>

        <SubSection title={t.docsSandboxLimits}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsSandboxLimitsDesc}</p>
          <ul className="list-disc pl-5 space-y-1.5 text-sm text-muted-foreground">
            <li>{t.docsSandboxLimit1}</li>
            <li>{t.docsSandboxLimit2}</li>
            <li>{t.docsSandboxLimit3}</li>
          </ul>
        </SubSection>

        <SubSection title={t.docsSandboxImportant}>
          <div className="rounded-lg border border-warning/30 bg-warning/5 p-4">
            <p className="text-sm font-medium text-warning mb-2">{t.docsSandboxImportantTitle}</p>
            <p className="text-sm text-muted-foreground">{t.docsSandboxImportantDesc}</p>
          </div>
        </SubSection>
      </Section>

      {/* ── Section 3: Configuration Reference ── */}
      <Section
        icon={<Cpu className="h-5 w-5" />}
        title={t.docsConfigTitle}
        expanded={expanded.config}
        onToggle={() => toggle("config")}
      >
        <SubSection title={t.docsConfigBacktest}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsConfigBacktestDesc}</p>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="text-left px-3 py-2 font-medium">{t.docsConfigColParam}</th>
                <th className="text-left px-3 py-2 font-medium">{t.docsConfigColType}</th>
                <th className="text-left px-3 py-2 font-medium">{t.docsConfigColDefault}</th>
                <th className="text-left px-3 py-2 font-medium">{t.docsConfigColDesc}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {[
                ["codes", "list[str]", "—", t.docsConfigCodes],
                ["start_date", "str", '"2024-01-01"', t.docsConfigStartDate],
                ["end_date", "str", '"2025-12-31"', t.docsConfigEndDate],
                ["source", "str", '"auto"', t.docsConfigSource],
                ["interval", "str", '"1D"', t.docsConfigInterval],
                ["initial_cash", "float", "100000", t.docsConfigCash],
                ["leverage", "float", "1.0", t.docsConfigLeverage],
                ["engine", "str", '"daily"', t.docsConfigEngine],
                ["extra_fields", "list[str]", "None", t.docsConfigExtraFields],
              ].map(([param, type, def, desc]) => (
                <tr key={param} className="hover:bg-muted/30 transition-colors">
                  <td className="px-3 py-2 font-mono text-xs">{param}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{type}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{def}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SubSection>

        <SubSection title={t.docsConfigIntervals}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsConfigIntervalsDesc}</p>
          <div className="flex flex-wrap gap-2 text-sm">
            {["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "4W"].map((i) => (
              <code key={i} className="px-3 py-1.5 rounded-md bg-muted/60 text-xs font-mono">{i}</code>
            ))}
          </div>
        </SubSection>

        <SubSection title={t.docsConfigSources}>
          <p className="text-sm text-muted-foreground mb-3">{t.docsConfigSourcesDesc}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            {[
              ["auto", t.docsConfigSourceAuto],
              ["akshare", t.docsConfigSourceAkshare],
              ["tushare", t.docsConfigSourceTushare],
              ["yfinance", t.docsConfigSourceYfinance],
              ["futu", t.docsConfigSourceFutu],
              ["tencent", t.docsConfigSourceTencent],
              ["ccxt", t.docsConfigSourceCcxt],
              ["coingecko", t.docsConfigSourceCoingecko],
              ["finnhub", t.docsConfigSourceFinnhub],
              ["twelvedata", t.docsConfigSourceTwelvedata],
              ["tiingo", t.docsConfigSourceTiingo],
              ["okx", t.docsConfigSourceOkx],
              ["global_indices", t.docsConfigSourceGlobalIndices],
              ["commodities", t.docsConfigSourceCommodities],
            ].map(([key, desc]) => (
              <div key={key} className="flex items-start gap-2 px-3 py-2 rounded-md bg-muted/40">
                <code className="text-xs font-mono text-primary shrink-0">{key}</code>
                <span className="text-xs text-muted-foreground">{desc}</span>
              </div>
            ))}
          </div>
        </SubSection>
      </Section>

    </div>
  );
}

/* ── Helper components ── */

function Section({
  icon,
  title,
  expanded,
  onToggle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors text-left"
      >
        <span className="text-primary">{icon}</span>
        <span className="font-semibold flex-1">{title}</span>
        {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
      </button>
      {expanded && <div className="px-4 pb-4 space-y-5">{children}</div>}
    </div>
  );
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}

function CodeBlock({ language, children }: { language: string; children: string }) {
  return (
    <pre className="rounded-lg bg-zinc-950 dark:bg-zinc-900 border p-4 overflow-x-auto text-xs leading-relaxed">
      <code className={`language-${language} text-zinc-100`}>{children}</code>
    </pre>
  );
}
