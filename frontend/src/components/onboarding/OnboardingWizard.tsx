import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { Bot, Database, Star, Target, Check } from "lucide-react";

interface Props {
  onComplete?: () => void;
  className?: string;
}

const STEPS = [
  { key: "welcome", icon: Bot, title: "Welcome", desc: "AStockPursue is an AI-powered quantitative trading research platform." },
  { key: "llm", icon: Bot, title: "Connect LLM", desc: "Configure your LLM provider to enable AI strategy generation." },
  { key: "datasource", icon: Database, title: "Data Sources", desc: "Set up market data providers for backtesting and live trading." },
  { key: "watchlist", icon: Star, title: "Build Watchlist", desc: "Add stocks you want to track and trade." },
  { key: "strategy", icon: Target, title: "First Strategy", desc: "Create your first trading strategy — describe it in natural language!" },
  { key: "done", icon: Check, title: "Ready!", desc: "You're all set to explore quantitative trading." },
] as const;

type StepKey = typeof STEPS[number]["key"];

export function OnboardingWizard({ onComplete, className }: Props) {
  const [current, setCurrent] = useState<StepKey>("welcome");
  const [completed, setCompleted] = useState<Set<StepKey>>(new Set(["welcome"]));
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [dsConfigured, setDsConfigured] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("onboarding-done");
    if (stored === "true") setDismissed(true);

    // Check existing config
    api.getLLMSettings().then((s: any) => {
      if (s?.provider && s?.provider !== "none") setLlmConfigured(true);
    }).catch(() => {});
    api.getDataSourceSettings().then((s: any) => {
      if (s?.tushare_token || s?.akshare_configured) setDsConfigured(true);
    }).catch(() => {});
  }, []);

  const markDone = (step: StepKey) => {
    setCompleted((prev) => new Set([...prev, step]));
  };

  const finish = () => {
    localStorage.setItem("onboarding-done", "true");
    setDismissed(true);
    onComplete?.();
  };

  const next = () => {
    markDone(current);
    const idx = STEPS.findIndex((s) => s.key === current);
    if (idx >= 0 && idx < STEPS.length - 1) {
      setCurrent(STEPS[idx + 1].key);
    } else {
      finish();
    }
  };

  if (dismissed) return null;

  const currStep = STEPS.find((s) => s.key === current)!;
  const Icon = currStep.icon;

  return (
    <div className={cn("fixed inset-0 bg-black/50 flex items-center justify-center z-50", className)}>
      <div className="bg-card border rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-xl">
        {/* Progress dots */}
        <div className="flex justify-center gap-1.5">
          {STEPS.filter((s) => s.key !== "done").map((s) => (
            <div
              key={s.key}
              className={cn(
                "w-2 h-2 rounded-full transition",
                completed.has(s.key) ? "bg-primary" : current === s.key ? "bg-primary/40 animate-pulse" : "bg-border"
              )}
            />
          ))}
        </div>

        {/* Content */}
        <div className="text-center space-y-3">
          <Icon className="w-10 h-10 mx-auto text-primary" />
          <h2 className="text-lg font-bold">{currStep.title}</h2>
          <p className="text-sm text-muted-foreground">{currStep.desc}</p>

          {current === "llm" && (
            <div className="text-xs space-y-1">
              {llmConfigured ? (
                <span className="text-success">✓ LLM already configured</span>
              ) : (
                <span className="text-muted-foreground">Go to Settings → LLM to add your API key</span>
              )}
            </div>
          )}
          {current === "datasource" && (
            <div className="text-xs space-y-1">
              {dsConfigured ? (
                <span className="text-success">✓ Data source configured</span>
              ) : (
                <span className="text-muted-foreground">Go to Settings → Data Sources to configure</span>
              )}
            </div>
          )}
          {current === "watchlist" && (
            <p className="text-xs text-muted-foreground">
              Open the Trading Dashboard and search for stocks to add to your watchlist.
            </p>
          )}
          {current === "strategy" && (
            <p className="text-xs text-muted-foreground">
              Go to the Agent page and describe your strategy idea — the AI will generate the code!
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-between pt-2">
          <button
            onClick={finish}
            className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            Skip
          </button>
          <div className="flex gap-2">
            {current !== "welcome" && (
              <button
                onClick={() => {
                  const idx = STEPS.findIndex((s) => s.key === current);
                  if (idx > 0) setCurrent(STEPS[idx - 1].key);
                }}
                className="px-4 py-1.5 text-xs rounded bg-muted hover:bg-muted/70"
              >
                Back
              </button>
            )}
            <button
              onClick={next}
              className="px-4 py-1.5 text-xs rounded bg-primary text-primary-foreground font-medium"
            >
              {current === "done" ? "Get Started" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
