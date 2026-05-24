import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Loader2 } from "lucide-react";

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "moonshot", label: "Moonshot (月之暗面)" },
  { value: "minimax", label: "MiniMax (海螺)" },
  { value: "zhipu", label: "智谱 (GLM)" },
  { value: "qwen", label: "通义千问 (Qwen)" },
  { value: "gemini", label: "Gemini" },
  { value: "groq", label: "Groq" },
  { value: "ollama", label: "Ollama (本地)" },
];

export function PostLoginSetup() {
  const [show, setShow] = useState(false);
  const [config, setConfig] = useState({ provider: "", model: "", baseUrl: "", apiKey: "" });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("vt_token");
    if (!token) return;
    fetch("/api/auth/llm-config", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => {
        const cfg = data.llm_config || {};
        if (!cfg.provider || !cfg.model) {
          setShow(true);
        } else {
          setConfig(cfg);
          setSaved(true);
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    if (!config.provider || !config.model) return;
    setLoading(true);
    const token = localStorage.getItem("vt_token");
    try {
      await fetch("/api/auth/llm-config", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(config),
      });
      setSaved(true);
      setTimeout(() => setShow(false), 1500);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  const handleSkip = () => { setShow(false); navigate("/settings"); };
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
      <div className="bg-card border rounded-xl shadow-2xl w-[500px] max-h-[85vh] overflow-auto p-6 space-y-5">
        <div className="text-center space-y-1.5">
          <BarChart3 className="mx-auto h-8 w-8 text-primary" />
          <h2 className="text-lg font-bold">{saved ? "已保存！" : "配置大语言模型"}</h2>
          <p className="text-sm text-muted-foreground">
            {saved ? "即将跳转到设置..." : "配置 LLM 提供商以开始 AI 量化研究"}
          </p>
        </div>

        {!saved && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">模型供应商</label>
              <select
                value={config.provider}
                onChange={(e) => setConfig({ ...config, provider: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1.5 text-xs"
              >
                <option value="">请选择...</option>
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium">模型名称</label>
              <input
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1.5 text-xs"
                placeholder="gpt-4o-mini / deepseek-chat / ..."
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium">Base URL（可选）</label>
              <input
                value={config.baseUrl}
                onChange={(e) => setConfig({ ...config, baseUrl: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1.5 text-xs"
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium">API Key</label>
              <input
                type="password"
                value={config.apiKey}
                onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1.5 text-xs"
                placeholder="sk-..."
              />
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={handleSkip} className="flex-1 rounded border px-4 py-2 text-xs text-muted-foreground hover:bg-muted transition">
                跳过，去设置
              </button>
              <button onClick={handleSave} disabled={!config.provider || !config.model || loading}
                className="flex-1 rounded bg-primary px-4 py-2 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2">
                {loading && <Loader2 className="h-3 w-3 animate-spin" />}
                保存并继续
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
