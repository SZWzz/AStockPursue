import { useI18n } from "@/lib/i18n";

interface ExampleCategory {
  titleKey: string;
  prompts: { titleKey: string; descKey: string; prompt: string }[];
}

export const EXAMPLE_CATEGORIES: ExampleCategory[] = [
  {
    titleKey: "welcomeCat_backtest",
    prompts: [
      {
        titleKey: "welcomeEx_multiMarket",
        descKey: "welcomeEx_multiMarket_desc",
        prompt: "Build a multi-market portfolio with 000001.SZ (A-share), AAPL (US), and BTC-USDT (crypto), backtest 2024, and compare their Sharpe ratios.",
      },
      {
        titleKey: "welcomeEx_macdBTC",
        descKey: "welcomeEx_macdBTC_desc",
        prompt: "Write a MACD crossover strategy for BTC-USDT, backtest 2024 with 1H bars, and calculate the profit factor.",
      },
      {
        titleKey: "welcomeEx_usTech",
        descKey: "welcomeEx_usTech_desc",
        prompt: "Backtest an equal-weight portfolio of AAPL, MSFT, GOOGL, AMZN, NVDA for 2024, compare against SPY as a benchmark.",
      },
    ],
  },
  {
    titleKey: "welcomeCat_research",
    prompts: [
      {
        titleKey: "welcomeEx_multiFactor",
        descKey: "welcomeEx_multiFactor_desc",
        prompt: "Design a multi-factor alpha model combining momentum, volatility, and volume factors. Backtest on 000001.SZ in 2024.",
      },
      {
        titleKey: "welcomeEx_options",
        descKey: "welcomeEx_options_desc",
        prompt: "Price a 30-day ATM call option on AAPL using Black-Scholes. Show the Greeks (delta, gamma, theta, vega).",
      },
    ],
  },
  {
    titleKey: "welcomeCat_analysis",
    prompts: [
      {
        titleKey: "welcomeEx_momentum",
        descKey: "welcomeEx_momentum_desc",
        prompt: "分析 600519.SH 近期走势，计算 RSI 和 MACD 指标，判断是否处于超买/超卖区域，给出交易建议。",
      },
      {
        titleKey: "welcomeEx_correlation",
        descKey: "welcomeEx_correlation_desc",
        prompt: "分析 BTC-USDT 和 ETH-USDT 的相关性，回测配对交易策略，计算年化收益和最大回撤。",
      },
    ],
  },
];

interface ExamplePromptsProps {
  onSelect: (prompt: string) => void;
}

export function ExamplePrompts({ onSelect }: ExamplePromptsProps) {
  const { t } = useI18n();

  return (
    <div className="flex-1 overflow-auto p-3 space-y-4">
      <div className="text-[11px] font-medium text-muted-foreground">{t.tryExamples || "试试这些"}</div>
      {EXAMPLE_CATEGORIES.map((cat) => (
        <div key={cat.titleKey} className="space-y-1.5">
          <div className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wide">
            {(t as Record<string, string>)[cat.titleKey] || cat.titleKey}
          </div>
          {cat.prompts.map((p) => (
            <button
              key={p.titleKey}
              onClick={() => onSelect(p.prompt)}
              className="w-full text-left px-2.5 py-2 rounded-md hover:bg-muted/50 transition border border-transparent hover:border-border/50 group"
            >
              <div className="text-xs font-medium truncate">
                {(t as Record<string, string>)[p.titleKey] || p.titleKey}
              </div>
              <div className="text-[10px] text-muted-foreground/70 line-clamp-2 mt-0.5">
                {(t as Record<string, string>)[p.descKey] || p.descKey}
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
