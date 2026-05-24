import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import type { RiskConfig } from "@/services/paperTrading";

interface Props {
  config: RiskConfig;
  onChange: (config: RiskConfig) => void;
  disabled?: boolean;
}

const defaultConfig: RiskConfig = {
  stop_loss_pct: 5.0,
  take_profit_pct: 10.0,
  trailing_stop_pct: 0,
  max_daily_loss_pct: 3.0,
  max_position_pct: 30.0,
};

export default function RiskConfigForm({ config, onChange, disabled }: Props) {
  const { t } = useI18n();
  const [local, setLocal] = useState<RiskConfig>({ ...defaultConfig, ...config });

  const update = (key: keyof RiskConfig, value: number) => {
    const next = { ...local, [key]: value };
    setLocal(next);
    onChange(next);
  };

  const fields: { key: keyof RiskConfig; labelKey: string; suffixKey?: string; step: number; min: number; max: number }[] = [
    { key: "stop_loss_pct", labelKey: "ptRiskStopLoss", step: 0.5, min: 0, max: 100 },
    { key: "take_profit_pct", labelKey: "ptRiskTakeProfit", step: 0.5, min: 0, max: 1000 },
    { key: "trailing_stop_pct", labelKey: "ptRiskTrailingStop", suffixKey: "ptRiskTrailingHint", step: 0.5, min: 0, max: 100 },
    { key: "max_daily_loss_pct", labelKey: "ptRiskMaxDailyLoss", step: 0.5, min: 0, max: 100 },
    { key: "max_position_pct", labelKey: "ptRiskMaxPosition", step: 5, min: 1, max: 100 },
  ];

  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="flex items-center gap-3">
          <label className="text-sm text-gray-600 w-28 shrink-0">{t[f.labelKey as keyof typeof t]}</label>
          <input
            type="range"
            min={f.min}
            max={f.max}
            step={f.step}
            value={local[f.key]}
            onChange={(e) => update(f.key, parseFloat(e.target.value))}
            disabled={disabled}
            className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <span className="text-sm font-mono w-16 text-right">
            {local[f.key]}{f.suffixKey ? t[f.suffixKey as keyof typeof t] : "%"}
          </span>
        </div>
      ))}
    </div>
  );
}

export { defaultConfig };
export type { RiskConfig };
