import { useI18n } from "@/lib/i18n";
import type { ParamDef } from "./types";

interface ParamPanelProps {
  params: ParamDef[];
  values: Record<string, string | number | boolean>;
  onChange: (name: string, value: string | number | boolean) => void;
}

export function ParamPanel({ params, values, onChange }: ParamPanelProps) {
  const { t } = useI18n();
  if (!params || params.length === 0) {
    return (
      <div className="text-xs text-muted-foreground p-3 text-center">
        {t.indicatorLabNoParams} <code className="bg-muted px-1 rounded text-[10px]"># @param</code>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {params.map((param) => (
        <div key={param.name} className="space-y-1">
          <label className="flex items-center justify-between text-xs">
            <span className="font-medium text-foreground">{param.name}</span>
            <span className="text-muted-foreground font-mono text-[10px]">{param.type}</span>
          </label>

          {param.description && (
            <p className="text-[10px] text-muted-foreground leading-tight">{param.description}</p>
          )}

          {param.type === "bool" ? (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!!values[param.name]}
                onChange={(e) => onChange(param.name, e.target.checked)}
                className="w-3.5 h-3.5 rounded border-muted-foreground/30"
              />
              <span className="text-xs text-muted-foreground">
                {values[param.name] ? "Enabled" : "Disabled"}
              </span>
            </label>
          ) : param.type === "int" ? (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={param.values?.[0] ?? 1}
                max={param.values?.[param.values.length - 1] ?? 100}
                step={1}
                value={Number(values[param.name] ?? param.default)}
                onChange={(e) => onChange(param.name, parseInt(e.target.value))}
                className="flex-1 h-1.5"
              />
              <span className="text-xs font-mono text-muted-foreground w-8 text-right tabular-nums">
                {String(values[param.name] ?? param.default)}
              </span>
            </div>
          ) : param.type === "float" ? (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={param.values?.[0] ?? 0}
                max={param.values?.[param.values.length - 1] ?? 1}
                step={0.01}
                value={Number(values[param.name] ?? param.default)}
                onChange={(e) => onChange(param.name, parseFloat(e.target.value))}
                className="flex-1 h-1.5"
              />
              <span className="text-xs font-mono text-muted-foreground w-12 text-right tabular-nums">
                {Number(values[param.name] ?? param.default).toFixed(2)}
              </span>
            </div>
          ) : param.values && param.values.length > 0 ? (
            <select
              value={String(values[param.name] ?? param.default)}
              onChange={(e) => onChange(param.name, e.target.value)}
              className="w-full text-xs rounded border border-border bg-background px-2 py-1"
            >
              {param.values.map((v) => (
                <option key={String(v)} value={String(v)}>
                  {String(v)}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={String(values[param.name] ?? param.default ?? "")}
              onChange={(e) => onChange(param.name, e.target.value)}
              className="w-full text-xs rounded border border-border bg-background px-2 py-1 font-mono"
            />
          )}
        </div>
      ))}
    </div>
  );
}
