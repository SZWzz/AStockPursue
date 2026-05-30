import { useEffect, useState, useCallback } from "react";
import { Loader2, X, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type TradingOrder } from "@/lib/api";

interface Props {
  symbol: string;
  orders: TradingOrder[];
  loading: boolean;
  onRefresh: () => void;
}

type Tab = "active" | "history";

/** Order entry form + active orders list + history. */
export function OrderPanel({ symbol, orders, loading, onRefresh }: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("active");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [qty, setQty] = useState("100");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { onRefresh(); }, [onRefresh]);

  const handleSubmit = async () => {
    if (!symbol) { setMsg("请先选择标的"); return; }
    const qtyNum = Number(qty);
    if (isNaN(qtyNum) || qtyNum <= 0) { setMsg("数量必须为正数"); return; }
    if (orderType === "limit") {
      const priceNum = Number(price);
      if (isNaN(priceNum) || priceNum <= 0) { setMsg("限价单需要填写价格"); return; }
    }
    setSubmitting(true);
    setMsg(null);
    try {
      await api.createOrder({
        symbol,
        side,
        order_type: orderType,
        qty: qtyNum,
        ...(orderType === "limit" ? { price: Number(price) } : {}),
      });
      setMsg("下单成功");
      setQty("100");
      setPrice("");
      onRefresh();
    } catch (e) {
      setMsg(String(e));
    }
    setSubmitting(false);
  };

  const cancelOrder = useCallback(async (orderId: number) => {
    try {
      await api.cancelOrder(orderId);
      onRefresh();
    } catch { /* ignore */ }
  }, [onRefresh]);

  const activeOrders = orders.filter((o) => o.status === "active");
  const historyOrders = orders.filter((o) => o.status !== "active");
  const displayed = tab === "active" ? activeOrders : historyOrders;

  return (
    <div className="flex flex-col h-full">
      {/* Order form */}
      <div className="p-3 border-b space-y-2 shrink-0">
        <div className="text-xs font-medium text-muted-foreground">
          {t.tradingOrderPanel || "下单"} {symbol && <span className="font-mono text-foreground">{symbol}</span>}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setSide("buy")}
            className={cn("flex-1 py-1.5 text-xs rounded font-medium transition", side === "buy" ? "bg-up text-white" : "bg-muted text-muted-foreground")}
          >
            {t.tradingOrderSideBuy || "买入"}
          </button>
          <button
            onClick={() => setSide("sell")}
            className={cn("flex-1 py-1.5 text-xs rounded font-medium transition", side === "sell" ? "bg-down text-white" : "bg-muted text-muted-foreground")}
          >
            {t.tradingOrderSideSell || "卖出"}
          </button>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOrderType("market")}
            className={cn("flex-1 py-1 text-xs rounded border transition", orderType === "market" ? "border-primary text-primary bg-primary/5" : "border-border text-muted-foreground")}
          >
            {t.tradingOrderTypeMarket || "市价"}
          </button>
          <button
            onClick={() => setOrderType("limit")}
            className={cn("flex-1 py-1 text-xs rounded border transition", orderType === "limit" ? "border-primary text-primary bg-primary/5" : "border-border text-muted-foreground")}
          >
            {t.tradingOrderTypeLimit || "限价"}
          </button>
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="数量"
            className="flex-1 text-xs rounded border px-2 py-1.5 bg-background"
          />
          {orderType === "limit" && (
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="价格"
              className="w-24 text-xs rounded border px-2 py-1.5 bg-background"
              step="0.01"
            />
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={submitting || !symbol}
          className={cn(
            "w-full py-1.5 text-xs rounded font-medium transition flex items-center justify-center gap-1",
            side === "buy" ? "bg-up text-white hover:bg-up/90" : "bg-down text-white hover:bg-down/90",
            (!symbol || submitting) && "opacity-50 cursor-not-allowed"
          )}
        >
          {submitting && <Loader2 className="h-3 w-3 animate-spin" />}
          {side === "buy" ? (t.tradingOrderSideBuy || "买入") : (t.tradingOrderSideSell || "卖出")} {symbol || ""}
        </button>
        {msg && <div className="text-[10px] text-muted-foreground text-center">{msg}</div>}
      </div>

      {/* Tab bar */}
      <div className="flex border-b shrink-0">
        {(["active", "history"] as Tab[]).map((tb) => (
          <button
            key={tb}
            onClick={() => setTab(tb)}
            className={cn(
              "flex-1 py-1.5 text-xs font-medium transition border-b-2",
              tab === tb ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tb === "active" ? (t.tradingOrderActive || "活跃订单") : (t.tradingOrderHistory || "历史订单")}
            {tb === "active" && activeOrders.length > 0 && (
              <span className="ml-1 text-[10px]">({activeOrders.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Order list */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
        ) : displayed.length === 0 ? (
          <div className="p-4 text-center text-[11px] text-muted-foreground/60">
            {tab === "active" ? "无活跃订单" : "无历史订单"}
          </div>
        ) : (
          displayed.map((o) => (
            <div key={o.id} className="flex items-center gap-2 px-3 py-2 border-b border-border/30 text-xs">
              <span className={cn("w-8 font-medium", o.side === "buy" ? "text-up" : "text-down")}>
                {o.side === "buy" ? "买" : "卖"}
              </span>
              <span className="font-mono flex-1">{o.symbol}</span>
              <span className="text-muted-foreground">{o.order_type === "market" ? "市价" : "限价"}</span>
              <span>{o.qty}股</span>
              {o.order_type === "limit" && <span>@{o.price}</span>}
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[10px]",
                o.status === "active" ? "bg-warning/10 text-warning" : o.status === "filled" ? "bg-up/10 text-up" : "bg-muted text-muted-foreground"
              )}>
                {o.status === "active" ? "活跃" : o.status === "filled" ? "已成交" : "已撤"}
              </span>
              {o.status === "active" && (
                <button onClick={() => cancelOrder(o.id)} className="text-muted-foreground hover:text-danger">
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
