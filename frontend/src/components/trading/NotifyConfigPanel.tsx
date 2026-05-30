import { useEffect, useState, useCallback } from "react";
import { Loader2, Plus, X, Save, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type NotifyConfig, type NotifyChannel } from "@/lib/api";

/** Notification configuration panel with channel CRUD and test-send. */
export function NotifyConfigPanel() {
  const { t } = useI18n();
  const [config, setConfig] = useState<NotifyConfig>({ enabled: false, channels: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const c = await api.getNotifyConfig();
      setConfig({ enabled: c.enabled ?? false, channels: c.channels ?? [] });
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.updateNotifyConfig(config);
      setMsg("保存成功");
    } catch (e) {
      setMsg(String(e));
    }
    setSaving(false);
  };

  const testSend = async (channel: NotifyChannel) => {
    try {
      const res = await api.testNotify(channel.type, channel.target);
      setMsg(res.message || res.error || "已发送");
    } catch (e) {
      setMsg(String(e));
    }
  };

  const addChannel = () => {
    setConfig((prev) => ({
      ...prev,
      channels: [...(prev.channels || []), { type: "email", target: "", enabled: true }],
    }));
  };

  const updateChannel = (idx: number, patch: Partial<NotifyChannel>) => {
    setConfig((prev) => ({
      ...prev,
      channels: prev.channels?.map((ch, i) => (i === idx ? { ...ch, ...patch } : ch)) || [],
    }));
  };

  const removeChannel = (idx: number) => {
    setConfig((prev) => ({
      ...prev,
      channels: prev.channels?.filter((_, i) => i !== idx) || [],
    }));
  };

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="flex flex-col h-full p-3 space-y-3 overflow-auto">
      {/* Enable toggle */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">{t.tradingNotifyEnabled || "启用通知"}</span>
        <button
          onClick={() => setConfig((p) => ({ ...p, enabled: !p.enabled }))}
          className={cn(
            "w-10 h-5 rounded-full transition relative",
            config.enabled ? "bg-primary" : "bg-muted"
          )}
        >
          <div className={cn(
            "w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all shadow",
            config.enabled ? "left-5" : "left-0.5"
          )} />
        </button>
      </div>

      {/* Channel list */}
      <div className="space-y-2">
        {config.channels?.map((ch, idx) => (
          <div key={idx} className="border rounded-lg p-2 space-y-1.5">
            <div className="flex items-center gap-2">
              <select
                value={ch.type}
                onChange={(e) => updateChannel(idx, { type: e.target.value })}
                className="text-xs rounded border px-2 py-1 bg-background"
              >
                <option value="email">Email</option>
                <option value="webhook">Webhook</option>
                <option value="sms">SMS</option>
              </select>
              <input
                type="text"
                value={ch.target}
                onChange={(e) => updateChannel(idx, { target: e.target.value })}
                placeholder="user@example.com 或 https://..."
                className="flex-1 text-xs rounded border px-2 py-1 bg-background"
              />
              <button onClick={() => testSend(ch)} className="p-1 text-muted-foreground hover:text-primary" title={t.tradingNotifyTest || "测试"}>
                <Send className="h-3 w-3" />
              </button>
              <button onClick={() => removeChannel(idx)} className="p-1 text-muted-foreground hover:text-danger">
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <button onClick={addChannel} className="flex items-center gap-1 text-xs text-primary hover:text-primary/80">
        <Plus className="h-3 w-3" /> {t.tradingNotifyChannel || "添加渠道"}
      </button>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-3 w-3 animate-spin" />}
          <Save className="h-3 w-3" /> {t.llmSaveSettings || "保存"}
        </button>
      </div>
      {msg && <div className="text-[10px] text-muted-foreground">{msg}</div>}
    </div>
  );
}
