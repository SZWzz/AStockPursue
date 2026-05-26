import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Sparkles, MessageSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { CorrelationMatrix } from "@/components/charts/CorrelationMatrix";
import { StockInput } from "@/components/indicator-lab/StockInput";
import { api } from "@/lib/api";

const STORAGE_KEY = "vr_correlation_result";
const WINDOWS = [30, 60, 90, 180, 365] as const;

interface SavedResult { labels: string[]; matrix: number[][]; days: number; method: string; codes: string; }

export function Correlation() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [codes, setCodes] = useState("600519.SH,000001.SZ,000858.SZ,BTC-USDT");
  const [days, setDays] = useState<number>(90);
  const [method, setMethod] = useState<"pearson" | "spearman">("pearson");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labels, setLabels] = useState<string[]>([]);
  const [matrix, setMatrix] = useState<number[][]>([]);
  const [savingSession, setSavingSession] = useState(false);
  const [sessionMsg, setSessionMsg] = useState<string | null>(null);

  // Restore saved result on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const r: SavedResult = JSON.parse(saved);
        setLabels(r.labels);
        setMatrix(r.matrix);
        setDays(r.days);
        setMethod(r.method as "pearson" | "spearman");
        setCodes(r.codes);
      }
    } catch { /* ignore */ }
  }, []);

  const compute = async () => {
    setError(null);
    setLoading(true);
    try {
      const result = await api.getCorrelation({ codes, days, method });
      setLabels(result.labels);
      setMatrix(result.matrix);
      // Persist to localStorage
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        labels: result.labels, matrix: result.matrix, days, method, codes,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to compute correlation");
    } finally {
      setLoading(false);
    }
  };

  const saveToChat = async () => {
    if (labels.length === 0) return;
    setSavingSession(true);
    setSessionMsg(null);
    try {
      // Build correlation summary
      const pairs: string[] = [];
      for (let i = 0; i < labels.length; i++) {
        for (let j = i + 1; j < labels.length; j++) {
          pairs.push(`${labels[i]} & ${labels[j]}: ${(matrix[i][j] * 100).toFixed(1)}%`);
        }
      }
      const content = `[相关性矩阵] ${codes} | ${days}天 ${method}\n${pairs.join("；")}`;

      // Create session and send message
      const session = await api.createSession(`相关性分析: ${codes}`);
      // We get back { session_id } — now send the message
      await api.sendMessage(session.session_id, content);
      setSessionMsg(t.correlationSavedToSession);
      // Navigate to agent with this session
      navigate(`/?session=${session.session_id}`);
    } catch (e) {
      setSessionMsg(`${t.correlationSaveFailed}: ${e}`);
    } finally {
      setSavingSession(false);
    }
  };

  const aiAnalyze = () => {
    const pairs: string[] = [];
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        pairs.push(`${labels[i]} & ${labels[j]}: ${(matrix[i][j] * 100).toFixed(1)}%`);
      }
    }
    localStorage.setItem("vr_pending_prompt", `分析以下资产相关性矩阵（${days}天 ${method}）：\n${pairs.join("；")}\n\n请分析：哪些资产正相关/负相关最强？如何利用这个相关性构建对冲组合？`);
    navigate("/");
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3">
        <BarChart3 className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">{t.correlation || "Correlation Matrix"}</h1>
      </div>

      <div className="flex flex-col gap-4 border rounded-lg p-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">{t.selectAssets || "Asset codes"}</label>
          <StockInput value={codes} onChange={setCodes} placeholder="600519.SH, 000001.SZ, BTC-USDT, AAPL" multi />
          <p className="text-xs text-muted-foreground">{t.correlationHint}</p>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">{t.windowLabel || "Window (days)"}</label>
            <div className="flex gap-1.5">
              {WINDOWS.map((w) => (
                <button key={w} onClick={() => setDays(w)} aria-pressed={days === w} className={`px-3 py-1.5 rounded text-sm border transition-colors ${days === w ? "bg-primary text-primary-foreground" : "border-muted-foreground/30 hover:border-primary"}`}>{w}d</button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">{t.methodLabel || "Method"}</label>
            <div className="flex gap-1.5">
              {(["pearson", "spearman"] as const).map((m) => (
                <button key={m} onClick={() => setMethod(m)} aria-pressed={method === m} className={`px-3 py-1.5 rounded text-sm border transition-colors capitalize ${method === m ? "bg-primary text-primary-foreground" : "border-muted-foreground/30 hover:border-primary"}`}>{m}</button>
              ))}
            </div>
          </div>
        </div>

        <button onClick={compute} disabled={loading} className="self-start px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
          {loading ? (t.loading || "Loading...") : (t.computeBtn || "Compute")}
        </button>
      </div>

      {error && <div className="text-sm text-danger border border-danger/30 rounded p-3 bg-danger/5">{error}</div>}

      {labels.length > 0 && (
        <>
          <CorrelationMatrix labels={labels} matrix={matrix} height={520} />
          <div className="flex items-center gap-3">
            <button onClick={aiAnalyze} className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition">
              <Sparkles className="h-4 w-4" />{t.correlationAIAnalyze}
            </button>
            <button onClick={saveToChat} disabled={savingSession} className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition disabled:opacity-50">
              <MessageSquare className="h-4 w-4" />{savingSession ? (t.llmSaving || "Saving...") : t.correlationSaveToSession}
            </button>
            {sessionMsg && <span className="text-xs text-muted-foreground">{sessionMsg}</span>}
          </div>
        </>
      )}
    </div>
  );
}
