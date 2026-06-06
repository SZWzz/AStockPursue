import { useEffect, useState, useCallback } from "react";
import { Loader2, Plus, X, Save, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type NotifyConfig, type NotifyChannel } from "@/lib/api";

const CHANNEL_TYPES = [
  { value: "telegram", label: "Telegram", extraFields: ["bot_token", "chat_id"] },
  { value: "discord", label: "Discord", extraFields: ["webhook_url"] },
  { value: "feishu", label: "Feishu / Lark", extraFields: ["webhook_url"] },
  { value: "webhook", label: "Webhook", extraFields: [] },
  { value: "email", label: "Email (SMTP)", extraFields: ["smtp_host", "smtp_port", "smtp_user", "smtp_pass"] },
];

const EXTRA_LABELS: Record<string, string> = {
  bot_token: "Bot Token", chat_id: "Chat ID", webhook_url: "Webhook URL",
  smtp_host: "SMTP Host", smtp_port: "SMTP Port", smtp_user: "Username", smtp_pass: "Password",
};

/** Notification configuration panel — multi-channel with extra fields per type. */
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
      setMsg(t.ptDeployFailed ? "" : "Saved");
    } catch (e) {
      setMsg(String(e));
    }
    setSaving(false);
  };

  const testSend = async (channel: NotifyChannel) => {
    try {
      const res = await api.testNotify(channel.type, channel.target);
      setMsg(res.message || res.error || "Sent");
    } catch (e) {
      setMsg(String(e));
    }
  };

  const addChannel = () => {
    setConfig((prev) => ({
      ...prev,
      channels: [...(prev.channels || []), { type: "telegram", target: "", enabled: true }],
    }));
  };

  const updateChannel = (idx: number, patch: Partial<NotifyChannel>) => {
    // Reset extra fields when type changes
    if (patch.type) {
      const ct = CHANNEL_TYPES.find((c) => c.value === patch.type);
      const reset: Partial<NotifyChannel> = {};
      for (const f of ["bot_token", "chat_id", "webhook_url", "smtp_host", "smtp_port", "smtp_user", "smtp_pass"]) {
        if (!ct?.extraFields.includes(f)) reset[f as keyof NotifyChannel] = undefined;
      }
      patch = { ...reset, ...patch };
    }
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
        <span className="text-xs font-medium">{t.tradingNotifyEnabled || "Enable Notifications"}</span>
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
        {config.channels?.map((ch, idx) => {
          const ct = CHANNEL_TYPES.find((c) => c.value === ch.type);
          return (
            <div key={idx} className="border rounded-lg p-2 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <select
                  value={ch.type}
                  onChange={(e) => updateChannel(idx, { type: e.target.value })}
                  className="text-xs rounded border px-1.5 py-1 bg-background w-28"
                >
                  {CHANNEL_TYPES.map((ct) => (
                    <option key={ct.value} value={ct.value}>{ct.label}</option>
                  ))}
                </select>
                <input
                  type="text"
                  value={ch.target}
                  onChange={(e) => updateChannel(idx, { target: e.target.value })}
                  placeholder={ch.type === "email" ? "user@example.com" : ch.type === "telegram" ? "Chat ID" : "https://..."}
                  className="flex-1 text-xs rounded border px-1.5 py-1 bg-background min-w-0"
                />
                <button onClick={() => testSend(ch)} className="p-1 text-muted-foreground hover:text-primary shrink-0" title={t.tradingNotifyTest || "Test"}>
                  <Send className="h-3 w-3" />
                </button>
                <button onClick={() => removeChannel(idx)} className="p-1 text-muted-foreground hover:text-down shrink-0">
                  <X className="h-3 w-3" />
                </button>
              </div>
              {/* Extra fields per channel type */}
              {ct?.extraFields.map((field) => (
                <div key={field} className="flex items-center gap-1">
                  <span className="text-[10px] text-muted-foreground w-16 shrink-0">{EXTRA_LABELS[field] || field}</span>
                  <input
                    type={field.includes("pass") || field.includes("token") ? "password" : "text"}
                    value={String((ch as any)[field] || "")}
                    onChange={(e) => updateChannel(idx, { [field]: e.target.value } as any)}
                    placeholder={EXTRA_LABELS[field] || field}
                    className="flex-1 text-[11px] rounded border px-1.5 py-0.5 bg-background font-mono"
                  />
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <button onClick={addChannel} className="flex items-center gap-1 text-xs text-primary hover:text-primary/80">
        <Plus className="h-3 w-3" /> {t.tradingNotifyChannel || "Add Channel"}
      </button>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-3 w-3 animate-spin" />}
          <Save className="h-3 w-3" /> {t.llmSaveSettings || "Save"}
        </button>
      </div>
      {msg && <div className="text-[10px] text-muted-foreground">{msg}</div>}
    </div>
  );
}
