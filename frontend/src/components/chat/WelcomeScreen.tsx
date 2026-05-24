import { Bot, TrendingUp, Globe, Sparkles, Users, UserCircle2, NotebookPen } from "lucide-react";
import { useI18n } from "@/lib/i18n";

interface ExampleKey {
  titleKey: string;
  descKey: string;
  prompt: string;
}

interface CategoryKey {
  labelKey: string;
  icon: React.ReactNode;
  color: string;
  textColor: string;
  exampleKeys: ExampleKey[];
}

const CATEGORY_KEYS: CategoryKey[] = [
  {
    labelKey: "welcomeCat_multiMarket",
    icon: <TrendingUp className="h-4 w-4" />,
    color: "text-red-400 border-red-500/30 hover:border-red-500/60 hover:bg-red-500/5",
    textColor: "text-red-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_crossMarketTitle",
        descKey: "welcomeEx_crossMarketDesc",
        prompt: "Backtest a risk-parity portfolio of 000001.SZ, BTC-USDT, and AAPL for full-year 2024, compare against equal-weight baseline",
      },
      {
        titleKey: "welcomeEx_btcMacdTitle",
        descKey: "welcomeEx_btcMacdDesc",
        prompt: "Backtest BTC-USDT 5-minute MACD strategy, fast=12 slow=26 signal=9, last 30 days",
      },
      {
        titleKey: "welcomeEx_techDiversifyTitle",
        descKey: "welcomeEx_techDiversifyDesc",
        prompt: "Backtest AAPL, MSFT, GOOGL, AMZN, NVDA with max_diversification portfolio optimizer, full-year 2024",
      },
    ],
  },
  {
    labelKey: "welcomeCat_research",
    icon: <Sparkles className="h-4 w-4" />,
    color: "text-amber-400 border-amber-500/30 hover:border-amber-500/60 hover:bg-amber-500/5",
    textColor: "text-amber-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_multiFactorTitle",
        descKey: "welcomeEx_multiFactorDesc",
        prompt: "Build a multi-factor alpha model using momentum, reversal, volatility, and turnover on CSI 300 constituents with IC-weighted factor synthesis, backtest 2023-2024",
      },
      {
        titleKey: "welcomeEx_optionsTitle",
        descKey: "welcomeEx_optionsDesc",
        prompt: "Calculate option Greeks using Black-Scholes: spot=100, strike=105, risk-free rate=3%, vol=25%, expiry=90 days, analyze Delta/Gamma/Theta/Vega",
      },
    ],
  },
  {
    labelKey: "welcomeCat_swarm",
    icon: <Users className="h-4 w-4" />,
    color: "text-violet-400 border-violet-500/30 hover:border-violet-500/60 hover:bg-violet-500/5",
    textColor: "text-violet-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_committeeTitle",
        descKey: "welcomeEx_committeeDesc",
        prompt: "[Swarm Team Mode] Use the investment_committee preset to evaluate whether to go long or short on NVDA given current market conditions",
      },
      {
        titleKey: "welcomeEx_quantDeskTitle",
        descKey: "welcomeEx_quantDeskDesc",
        prompt: "[Swarm Team Mode] Use the quant_strategy_desk preset to find and backtest the best momentum strategy on CSI 300 constituents",
      },
    ],
  },
  {
    labelKey: "welcomeCat_docResearch",
    icon: <Globe className="h-4 w-4" />,
    color: "text-blue-400 border-blue-500/30 hover:border-blue-500/60 hover:bg-blue-500/5",
    textColor: "text-blue-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_earningsTitle",
        descKey: "welcomeEx_earningsDesc",
        prompt: "Summarize the key financial metrics, risks, and outlook from the uploaded earnings report",
      },
      {
        titleKey: "welcomeEx_macroTitle",
        descKey: "welcomeEx_macroDesc",
        prompt: "Read the latest Fed meeting minutes and summarize the key takeaways for equity and crypto markets",
      },
    ],
  },
  {
    labelKey: "welcomeCat_journal",
    icon: <NotebookPen className="h-4 w-4" />,
    color: "text-orange-400 border-orange-500/30 hover:border-orange-500/60 hover:bg-orange-500/5",
    textColor: "text-orange-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_journalTitle",
        descKey: "welcomeEx_journalDesc",
        prompt: "Analyze the trade journal I just uploaded — full profile with holding stats, win rate, top symbols, and hourly distribution",
      },
      {
        titleKey: "welcomeEx_behaviorTitle",
        descKey: "welcomeEx_behaviorDesc",
        prompt: "Run the 4 behavior diagnostics on my trade journal (disposition, overtrading, chasing, anchoring) and tell me which bias hurts my PnL most",
      },
    ],
  },
  {
    labelKey: "welcomeCat_shadow",
    icon: <UserCircle2 className="h-4 w-4" />,
    color: "text-emerald-400 border-emerald-500/30 hover:border-emerald-500/60 hover:bg-emerald-500/5",
    textColor: "text-emerald-400",
    exampleKeys: [
      {
        titleKey: "welcomeEx_trainShadowTitle",
        descKey: "welcomeEx_trainShadowDesc",
        prompt: "Train my shadow account from the trading journal I just uploaded — show the extracted rules and confirm they look like my behavior",
      },
      {
        titleKey: "welcomeEx_pnlDeltaTitle",
        descKey: "welcomeEx_pnlDeltaDesc",
        prompt: "Run a shadow backtest for the last 90 days on the US market and break down where my PnL diverged from the shadow (rule violations, early exits, missed signals)",
      },
      {
        titleKey: "welcomeEx_shadowReportTitle",
        descKey: "welcomeEx_shadowReportDesc",
        prompt: "Render the shadow report and give me the URL — lead with the you-vs-shadow delta",
      },
    ],
  },
];

const CHIP_KEYS = [
  "welcomeChip1",
  "welcomeChip2",
  "welcomeChip3",
  "welcomeChip4",
  "welcomeChip5",
  "welcomeChip6",
  "welcomeChip7",
  "welcomeChip8",
  "welcomeChip9",
  "welcomeChip10",
  "welcomeChip11",
  "welcomeChip12",
  "welcomeChip13",
  "welcomeChip14",
];

interface Props {
  onExample: (s: string) => void;
}

export function WelcomeScreen({ onExample }: Props) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8 text-center">
      {/* Header */}
      <div className="space-y-3">
        <div className="h-16 w-16 mx-auto rounded-2xl bg-gradient-to-br from-primary/80 to-info/80 flex items-center justify-center shadow-lg">
          <Bot className="h-8 w-8 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">AStockPursue</h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto leading-relaxed">
            {t.welcomeTagline}
          </p>
          <p className="text-sm text-muted-foreground mt-2 max-w-md leading-relaxed mx-auto">
            {t.describeStrategy}
          </p>
        </div>
      </div>

      {/* Capability chips */}
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {CHIP_KEYS.map((key) => (
          <span
            key={key}
            className="px-2.5 py-1 text-xs rounded-full border border-border/60 text-muted-foreground bg-muted/30"
          >
            {(t as Record<string, string>)[key] || key}
          </span>
        ))}
      </div>

      {/* Example categories grid */}
      <div className="w-full max-w-2xl text-left space-y-4">
        <p className="text-xs text-muted-foreground px-1">{t.examples}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CATEGORY_KEYS.map((cat) => (
            <div key={cat.labelKey} className="space-y-2">
              <div className={`flex items-center gap-1.5 text-xs font-medium px-1 ${cat.textColor}`}>
                {cat.icon}
                <span>{(t as Record<string, string>)[cat.labelKey] || cat.labelKey}</span>
              </div>
              <div className="space-y-1.5">
                {cat.exampleKeys.map((ex) => (
                  <button
                    key={ex.titleKey}
                    onClick={() => onExample(ex.prompt)}
                    className={`block w-full text-left px-3 py-2.5 rounded-xl border transition-colors ${cat.color}`}
                  >
                    <span className="text-sm font-medium text-foreground leading-snug">
                      {(t as Record<string, string>)[ex.titleKey] || ex.titleKey}
                    </span>
                    <span className="block text-xs text-muted-foreground mt-0.5 leading-snug">
                      {(t as Record<string, string>)[ex.descKey] || ex.descKey}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
