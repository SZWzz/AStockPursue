import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Database, KeyRound, Loader2, RotateCcw, Save, Server, SlidersHorizontal, User } from "lucide-react";
import { toast } from "sonner";
import { api, type DataSourceSettings, type LLMProviderOption, type LLMSettings } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface LLMFormState {
  provider: string;
  model_name: string;
  base_url: string;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  reasoning_effort: string;
}

const fieldClass =
  "w-full rounded-md border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60";
const labelClass = "text-sm font-medium";
const hintClass = "text-xs text-muted-foreground";

function toForm(settings: LLMSettings): LLMFormState {
  return {
    provider: settings.provider,
    model_name: settings.model_name,
    base_url: settings.base_url,
    temperature: settings.temperature,
    timeout_seconds: settings.timeout_seconds,
    max_retries: settings.max_retries,
    reasoning_effort: settings.reasoning_effort || "",
  };
}

export function Settings() {
  const { t } = useI18n();
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [dataSettings, setDataSettings] = useState<DataSourceSettings | null>(null);
  const [form, setForm] = useState<LLMFormState | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [tushareToken, setTushareToken] = useState("");
  const [clearTushareToken, setClearTushareToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dataSaving, setDataSaving] = useState(false);
  const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
  const [userLlmConfig, setUserLlmConfig] = useState<Record<string, string> | null>(null);
  const [syncingUser, setSyncingUser] = useState(false);

  // Load per-user LLM config when logged in
  useEffect(() => {
    const token = localStorage.getItem("vt_token");
    if (!token) return;
    fetch("/api/auth/llm-config", { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => setUserLlmConfig(d.llm_config || {}));
  }, []);

  // Sync LLM + data source to user account
  const syncToUser = async () => {
    const token = localStorage.getItem("vt_token");
    if (!token || !userLlmConfig) return;
    setSyncingUser(true);
    try {
      // Sync LLM
      if (form) {
        await fetch("/api/auth/llm-config", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ provider: form.provider, model: form.model_name, base_url: form.base_url }),
        });
      }
      // Sync data source
      await fetch("/api/auth/data-source-config", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tushare_token: tushareToken || undefined }),
      });
      setUserLlmConfig({ ...userLlmConfig, provider: form?.provider || "", model: form?.model_name || "" });
    } catch { /* ignore */ }
    finally { setSyncingUser(false); }
  };

  useEffect(() => {
    let alive = true;
    Promise.all([api.getLLMSettings(), api.getDataSourceSettings()])
      .then(async ([llmData, dataSourceData]) => {
        if (!alive) return;
        // Overlay per-user LLM config from PG if logged in
        const token = localStorage.getItem("vt_token");
        if (token) {
          try {
            const res = await fetch("/api/auth/llm-config", { headers: { Authorization: `Bearer ${token}` } });
            const userCfg = await res.json();
            const cfg = userCfg.llm_config || {};
            if (cfg.provider) llmData.provider = cfg.provider;
            if (cfg.model) llmData.model_name = cfg.model;
            if (cfg.base_url) llmData.base_url = cfg.base_url;
          } catch { /* ignore */ }
        }
        setSettings(llmData);
        setForm(toForm(llmData));
        setDataSettings(dataSourceData);
        setSettingsLoadError(null);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : t.unknownError;
        setSettingsLoadError(message);
        toast.error(`${t.llmSettingsLoadFailed}: ${message}`);
        toast.error(`${t.dataSourceSettingsLoadFailed}: ${message}`);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, [t.dataSourceSettingsLoadFailed, t.llmSettingsLoadFailed]);

  const providers = settings?.providers ?? [];
  const selectedProvider = useMemo<LLMProviderOption | undefined>(
    () => providers.find((provider) => provider.name === form?.provider),
    [form?.provider, providers],
  );

  const applyProviderDefaults = (provider = selectedProvider) => {
    if (!provider || !form) return;
    setForm({
      ...form,
      model_name: provider.default_model,
      base_url: provider.default_base_url,
    });
  };

  const onProviderChange = (name: string) => {
    const provider = providers.find((item) => item.name === name);
    if (!provider || !form) return;
    setForm({
      ...form,
      provider: provider.name,
      model_name: provider.default_model,
      base_url: provider.default_base_url,
    });
    setApiKey("");
    setClearApiKey(false);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    try {
      const updated = await api.updateLLMSettings({
        ...form,
        api_key: apiKey.trim() || undefined,
        clear_api_key: clearApiKey,
      });
      setSettings(updated);
      setForm(toForm(updated));
      setApiKey("");
      setClearApiKey(false);
      toast.success(t.llmSettingsSaved);
    } catch (error) {
      toast.error(`${t.llmSettingsSaveFailed}: ${error instanceof Error ? error.message : t.unknownError}`);
    } finally {
      setSaving(false);
    }
  };

  const submitDataSources = async (event: FormEvent) => {
    event.preventDefault();
    setDataSaving(true);
    try {
      const updated = await api.updateDataSourceSettings({
        tushare_token: tushareToken.trim() || undefined,
        clear_tushare_token: clearTushareToken,
      });
      setDataSettings(updated);
      setTushareToken("");
      setClearTushareToken(false);
      toast.success(t.dataSourceSettingsSaved);
    } catch (error) {
      toast.error(`${t.dataSourceSettingsSaveFailed}: ${error instanceof Error ? error.message : t.unknownError}`);
    } finally {
      setDataSaving(false);
    }
  };

  const [changingPw, setChangingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<string | null>(null);
  const [changingUser, setChangingUser] = useState(false);
  const [userMsg, setUserMsg] = useState<string | null>(null);

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const oldPw = (form.elements.namedItem("old_password") as HTMLInputElement).value;
    const newPw = (form.elements.namedItem("new_password") as HTMLInputElement).value;
    setChangingPw(true); setPwMsg(null);
    try {
      const token = localStorage.getItem("vt_token");
      const res = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
      });
      const data = await res.json();
      if (res.ok) { setPwMsg("密码已更新，下次登录生效"); form.reset(); }
      else setPwMsg(data.detail || "修改失败");
    } catch { setPwMsg("网络错误"); }
    finally { setChangingPw(false); }
  };

  const changeUsername = async (e: FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const newName = (form.elements.namedItem("new_username") as HTMLInputElement).value;
    setChangingUser(true); setUserMsg(null);
    try {
      const token = localStorage.getItem("vt_token");
      const res = await fetch("/api/auth/change-username", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ username: newName }),
      });
      const data = await res.json();
      if (res.ok) {
        setUserMsg("用户名已更新");
        // Update stored user info
        const u = JSON.parse(localStorage.getItem("vt_user") || "{}");
        u.username = newName;
        localStorage.setItem("vt_user", JSON.stringify(u));
      }
      else setUserMsg(data.detail || "修改失败");
    } catch { setUserMsg("网络错误"); }
    finally { setChangingUser(false); }
  };

  const loggedIn = !!localStorage.getItem("vt_token");
  const userLlmSection = loggedIn && userLlmConfig ? (
    <div className="rounded-lg border bg-card p-4 shadow-sm mb-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium">{t.strategyLab || "My Account"} LLM</span>
          {userLlmConfig.provider ? (
            <span className="ml-2 text-xs text-success">{userLlmConfig.provider} / {userLlmConfig.model}</span>
          ) : (
            <span className="ml-2 text-xs text-warning">Not configured</span>
          )}
        </div>
        <button
          onClick={syncToUser}
          disabled={syncingUser}
          className="px-3 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50"
        >
          {syncingUser ? "Syncing..." : "Sync to my account"}
        </button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Save LLM and data source settings to your account. Other devices will use these automatically.
      </p>
    </div>
  ) : null;

  const accountSection = loggedIn ? (
    <div className="rounded-lg border bg-card p-5 shadow-sm mb-4 space-y-4">
      <div className="flex items-center gap-2">
        <User className="h-4 w-4 text-primary" />
        <h2 className="text-base font-semibold">账户设置</h2>
      </div>
      <form onSubmit={changeUsername} className="flex gap-2 items-end">
        <label className="grid gap-1 flex-1">
          <span className="text-xs font-medium">用户名</span>
          <input name="new_username" required minLength={2} placeholder={JSON.parse(localStorage.getItem("vt_user") || "{}").username || ""} className="rounded border bg-background px-2 py-1.5 text-sm" />
        </label>
        <button type="submit" disabled={changingUser} className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground disabled:opacity-50">
          {changingUser ? "..." : "修改"}
        </button>
        {userMsg && <span className={`text-xs ${userMsg.includes("失败") ? "text-danger" : "text-success"}`}>{userMsg}</span>}
      </form>
      <form onSubmit={changePassword} className="flex gap-2 items-end">
        <label className="grid gap-1 flex-1">
          <span className="text-xs font-medium">当前密码</span>
          <input name="old_password" type="password" required className="rounded border bg-background px-2 py-1.5 text-sm" />
        </label>
        <label className="grid gap-1 flex-1">
          <span className="text-xs font-medium">新密码</span>
          <input name="new_password" type="password" required minLength={4} className="rounded border bg-background px-2 py-1.5 text-sm" />
        </label>
        <button type="submit" disabled={changingPw} className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground disabled:opacity-50">
          {changingPw ? "..." : "修改"}
        </button>
        {pwMsg && <span className={`text-xs ${pwMsg.includes("失败") || pwMsg.includes("错误") ? "text-danger" : "text-success"}`}>{pwMsg}</span>}
      </form>
    </div>
  ) : null;

  if (loading || !form || !settings || !dataSettings) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{t.settings}</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">{t.settingsDesc}</p>
        </div>
        {accountSection}
        {userLlmSection}
        <div className="flex min-h-32 items-center justify-center rounded-lg border bg-card p-5 text-sm text-muted-foreground">
          {settingsLoadError ? (
            <div className="max-w-md text-center space-y-3">
              <div className="font-medium text-foreground">{t.settingsUnavailable}</div>
              <div className="mt-1">{settingsLoadError}</div>
              <div className="text-xs text-muted-foreground/80">{t.authRequiredHint}</div>
            </div>
          ) : (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {t.loading}
            </>
          )}
        </div>
      </div>
    );
  }

  const keyStatus = settings.api_key_configured
    ? t.llmApiKeyConfigured
    : settings.api_key_required
      ? t.llmApiKeyPlaceholder
      : selectedProvider?.auth_type === "oauth" && selectedProvider.login_command
        ? t.llmOauthRequired.replace("{command}", selectedProvider.login_command)
        : t.llmNoApiKeyRequired;
  const apiKeyDisabled = !selectedProvider?.api_key_required || clearApiKey;
  const tushareStatus = dataSettings.tushare_token_configured
    ? t.tushareTokenConfigured
    : t.tushareTokenPlaceholder;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t.settings}</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">{t.settingsDesc}</p>
      </div>

      {accountSection}

      <div className="space-y-2">
        <h2 className="text-lg font-semibold tracking-tight">{t.llmSettings}</h2>
        <p className="max-w-3xl text-sm text-muted-foreground">{t.llmSettingsDesc}</p>
      </div>

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <section className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="mb-5 flex items-center gap-2">
            <Server className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">{t.llmConnection}</h2>
          </div>

          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className={labelClass}>{t.llmProvider}</span>
              <select
                value={form.provider}
                onChange={(event) => onProviderChange(event.target.value)}
                className={fieldClass}
              >
                {providers.map((provider) => (
                  <option key={provider.name} value={provider.name}>{provider.label}</option>
                ))}
              </select>
              <span className={hintClass}>{t.llmProviderHint}</span>
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>{t.llmModelName}</span>
              <div className="flex gap-2">
                <input
                  value={form.model_name}
                  onChange={(event) => setForm({ ...form, model_name: event.target.value })}
                  className={fieldClass}
                  required
                />
                <button
                  type="button"
                  onClick={() => applyProviderDefaults()}
                  className="inline-flex shrink-0 items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
                  title={t.llmUseProviderDefaults}
                >
                  <RotateCcw className="h-4 w-4" />
                  <span className="hidden sm:inline">{t.llmUseProviderDefaults}</span>
                </button>
              </div>
              <span className={hintClass}>{t.llmModelHint}</span>
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>{t.llmBaseUrl}</span>
              <input
                value={form.base_url}
                onChange={(event) => setForm({ ...form, base_url: event.target.value })}
                className={fieldClass}
                placeholder={selectedProvider?.default_base_url}
                disabled={selectedProvider?.auth_type === "oauth"}
              />
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>
                {selectedProvider?.auth_type === "oauth" ? "OAuth" : t.llmApiKey}
              </span>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  className={`${fieldClass} pl-9`}
                  placeholder={keyStatus}
                  autoComplete="current-password"
                  disabled={apiKeyDisabled}
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className={hintClass}>{keyStatus}</span>
                {selectedProvider?.api_key_required ? (
                  <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={clearApiKey}
                      onChange={(event) => {
                        setClearApiKey(event.target.checked);
                        if (event.target.checked) setApiKey("");
                      }}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    {t.llmClearApiKey}
                  </label>
                ) : null}
              </div>
            </label>
          </div>
        </section>

        <section className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="mb-5 flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">{t.llmGeneration}</h2>
          </div>

          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className={labelClass}>{t.llmTemperature}</span>
              <input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature}
                onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })}
                className={fieldClass}
              />
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>{t.llmTimeoutSeconds}</span>
              <input
                type="number"
                min={1}
                max={3600}
                step={1}
                value={form.timeout_seconds}
                onChange={(event) => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
                className={fieldClass}
              />
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>{t.llmMaxRetries}</span>
              <input
                type="number"
                min={0}
                max={20}
                step={1}
                value={form.max_retries}
                onChange={(event) => setForm({ ...form, max_retries: Number(event.target.value) })}
                className={fieldClass}
              />
            </label>

            <label className="grid gap-2">
              <span className={labelClass}>{t.llmReasoningEffort}</span>
              <select
                value={form.reasoning_effort}
                onChange={(event) => setForm({ ...form, reasoning_effort: event.target.value })}
                className={fieldClass}
              >
                <option value="">{t.llmReasoningOff}</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="max">max</option>
              </select>
            </label>

            <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{t.llmEnvPath}: </span>
              <span className="break-all font-mono">{settings.env_path}</span>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? t.llmSaving : t.llmSaveSettings}
            </button>
          </div>
        </section>
      </form>

      <form onSubmit={submitDataSources} className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="mb-5 space-y-1">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">{t.dataSourceSettings}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{t.dataSourceSettingsDesc}</p>
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className={labelClass}>{t.tushareToken}</span>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  value={tushareToken}
                  onChange={(event) => setTushareToken(event.target.value)}
                  className={`${fieldClass} pl-9`}
                  placeholder={tushareStatus}
                  autoComplete="current-password"
                  disabled={clearTushareToken}
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className={hintClass}>{t.tushareTokenHint}</span>
                <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={clearTushareToken}
                    onChange={(event) => {
                      setClearTushareToken(event.target.checked);
                      if (event.target.checked) setTushareToken("");
                    }}
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  {t.clearTushareToken}
                </label>
              </div>
            </label>

            <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{t.llmEnvPath}: </span>
              <span className="break-all font-mono">{dataSettings.env_path}</span>
            </div>

            <button
              type="submit"
              disabled={dataSaving}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {dataSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {dataSaving ? t.llmSaving : t.saveDataSourceSettings}
            </button>
          </div>

          <div className="rounded-md border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="text-sm font-medium">{t.akshareStatus}</span>
                {dataSettings.akshare_available && dataSettings.akshare_version && (
                  <span className="ml-1.5 text-xs text-muted-foreground">v{dataSettings.akshare_version}</span>
                )}
              </div>
              <span className={`rounded-full px-2 py-0.5 text-xs ${dataSettings.akshare_available ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}>
                {dataSettings.akshare_available ? t.akshareAvailable : t.akshareNotAvailable}
              </span>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {dataSettings.akshare_available
                ? "Indicator Lab & Strategy Lab 可直接用于 A 股回测，无需额外配置。"
                : "Indicator Lab & Strategy Lab A 股回测需要 akshare，请 pip install akshare。"}
            </p>
          </div>
        </div>
      </form>
    </div>
  );
}
