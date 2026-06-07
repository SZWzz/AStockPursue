import { useI18n } from "@/lib/i18n";
import type { Position } from "@/services/paperTrading";

interface Props {
  positions: Position[];
  onClosePosition?: (symbol: string) => void;
}

export default function PositionTable({ positions, onClosePosition }: Props) {
  const { t } = useI18n();

  if (positions.length === 0) {
    return <div className="text-center text-muted-foreground py-8 text-sm">{t.ptNoPositions}</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-3">{t.ptSymbol}</th>
            <th className="py-2 pr-3">{t.ptDirection}</th>
            <th className="py-2 pr-3 text-right">{t.ptSize}</th>
            <th className="py-2 pr-3 text-right">{t.ptEntryPrice}</th>
            <th className="py-2 pr-3 text-right">{t.ptCurrentPrice}</th>
            <th className="py-2 pr-3 text-right">{t.ptUnrealizedPnl}</th>
            <th className="py-2 pr-3 text-right">{t.ptPnlPct}</th>
            {onClosePosition && <th className="py-2" />}
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr key={`${p.symbol}-${i}`} className="border-b last:border-0 hover:bg-muted/20">
              <td className="py-2 pr-3 font-mono font-medium">{p.symbol}</td>
              <td className="py-2 pr-3">
                <span
                  className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                    p.direction === 1 ? "bg-up/10 text-up" : "bg-down/10 text-down"
                  }`}
                >
                  {p.direction === 1 ? t.ptLong : t.ptShort}
                </span>
              </td>
              <td className="py-2 pr-3 text-right font-mono">{p.size.toFixed(0)}</td>
              <td className="py-2 pr-3 text-right font-mono">{p.entry_price.toFixed(3)}</td>
              <td className="py-2 pr-3 text-right font-mono">
                {p.current_price != null ? p.current_price.toFixed(3) : t.ptNA}
              </td>
              <td
                className={`py-2 pr-3 text-right font-mono ${
                  p.unrealized_pnl != null ? (p.unrealized_pnl >= 0 ? "text-up" : "text-down") : ""
                }`}
              >
                {p.unrealized_pnl != null
                  ? `${p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)}`
                  : t.ptNA}
              </td>
              <td
                className={`py-2 pr-3 text-right font-mono ${
                  p.pnl_pct != null ? (p.pnl_pct >= 0 ? "text-up" : "text-down") : ""
                }`}
              >
                {p.pnl_pct != null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(2)}%` : t.ptNA}
              </td>
              {onClosePosition && (
                <td className="py-2">
                  <button
                    className="px-2 py-0.5 text-xs bg-down/10 text-down rounded hover:bg-red-200"
                    onClick={() => onClosePosition(p.symbol)}
                  >
                    {t.ptClosePosition}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
