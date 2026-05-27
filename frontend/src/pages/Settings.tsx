import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, Database, KeyRound, Layers, Loader2, RotateCcw, Save, Server, SlidersHorizontal, Trash2, Upload, User } from "lucide-react";
import { toast } from "sonner";
import { api, type DataSourceSettings, type LLMProviderOption, type LLMSettings } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAuthStore } from "@/stores/auth";

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
  "w-full rounded-lg border bg-background px-3.5 py-2.5 text-sm outline-none transition-all duration-150 placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60";
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

interface SkillItem {
  name: string;
  description: string;
  category: string;
  enabled: boolean;
  source: "builtin" | "user";
}

function SkillSection() {
  const { t } = useI18n();
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);
  const [savingSkills, setSavingSkills] = useState(false);
  const [importing, setImporting] = useState(false);
  const [builtinOpen, setBuiltinOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadSkills = () => {
    api.getSkillSettings().then(d => { setSkills(d.skills); setSkillsLoading(false); }).catch(() => setSkillsLoading(false));
  };

  useEffect(() => { loadSkills(); }, []);

  const toggleSkill = (name: string) => {
    setSkills(prev => prev.map(s => s.name === name ? { ...s, enabled: !s.enabled } : s));
  };

  const saveSkills = async () => {
    setSavingSkills(true);
    const disabled = skills.filter(s => !s.enabled).map(s => s.name);
    try { await api.updateSkillSettings(disabled); toast.success(t.skillSaved || "已保存"); }
    catch { toast.error(t.skillSaveFailed || "保存失败"); }
    finally { setSavingSkills(false); }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const res = await api.importSkill(file);
      if (res.ok) { toast.success(`${t.skillImportOk || "已导入"}：${res.name}`); loadSkills(); }
      else { toast.error(t.skillImportFailed || "导入失败"); }
    } catch { toast.error(t.skillImportFailed || "导入失败"); }
    finally { setImporting(false); if (fileInputRef.current) fileInputRef.current.value = ""; }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`${t.skillDeleteConfirm || "确认删除技能"} "${name}"？`)) return;
    try {
      await api.deleteSkill(name);
      toast.success(`${t.skillDeleted || "已删除"}：${name}`);
      loadSkills();
    } catch { toast.error(t.skillDeleteFailed || "删除失败"); }
  };

  const builtinSkills = skills.filter(s => s.source !== "user");
  const userSkills = skills.filter(s => s.source === "user");
  const enabledCount = skills.filter(s => s.enabled).length;

  const renderSkillList = (list: SkillItem[]) => {
    const categories = [...new Set(list.map(s => s.category))].sort();
    return categories.map(cat => (
      <div key={cat}>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-1.5">{cat}</h4>
        <div className="space-y-1">
          {list.filter(s => s.category === cat).map(s => (
            <div key={s.name} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-muted/30 group">
              <label className="flex items-center min-w-0 cursor-pointer flex-1">
                <input type="checkbox" checked={s.enabled} onChange={() => toggleSkill(s.name)} className="mr-2 shrink-0 rounded" />
                <div className="min-w-0">
                  <span className="text-sm">{s.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground truncate">{s.description.slice(0, 60)}</span>
                </div>
              </label>
              {s.source === "user" && (
                <button onClick={() => handleDelete(s.name)} className="ml-2 p-0.5 rounded text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity" title={t.skillDelete}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    ));
  };

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
            <Layers className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h2 className="text-base font-semibold">{t.skillManagement}</h2>
            <p className="text-xs text-muted-foreground">{t.skillManagementDesc}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{t.skillTotal.replace("{total}", String(skills.length)).replace("{enabled}", String(enabledCount))}</span>
          <button onClick={saveSkills} disabled={savingSkills} className="btn-sm btn-primary">{savingSkills ? "保存中..." : "保存"}</button>
        </div>
      </div>

      {skillsLoading ? <div className="text-sm text-muted-foreground">加载中...</div> : (
        <>
          {/* Built-in skills — collapsible */}
          <div className="border rounded-lg">
            <button
              onClick={() => setBuiltinOpen(!builtinOpen)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/30 rounded-lg transition-colors"
            >
              <span className="text-sm font-medium">{t.skillBuiltin || "内置技能"} ({builtinSkills.length})</span>
              {builtinOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </button>
            {builtinOpen && <div className="px-3 pb-2 space-y-2">{renderSkillList(builtinSkills)}</div>}
          </div>

          {/* User-imported skills — collapsible, with import button */}
          <div className="border rounded-lg">
            <button
              onClick={() => setUserOpen(!userOpen)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/30 rounded-lg transition-colors"
            >
              <span className="text-sm font-medium">{t.skillUserImported || "用户导入"} ({userSkills.length})</span>
              <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                <input ref={fileInputRef} type="file" accept=".zip" onChange={handleImport} className="hidden" />
                <button onClick={() => fileInputRef.current?.click()} disabled={importing} className="btn-sm btn-secondary flex items-center gap-1 text-xs">
                  <Upload className="h-3 w-3" />
                  {importing ? "导入中..." : (t.skillImportBtn || "导入")}
                </button>
                {userOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
              </div>
            </button>
            {userOpen && (
              <div className="px-3 pb-2 space-y-2">
                {userSkills.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-2">{t.skillImportHint || "上传 .zip 文件（需包含 SKILL.md）"}</p>
                ) : (
                  renderSkillList(userSkills)
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function McpSection() {
  const { t } = useI18n();
  const [mcp, setMcp] = useState<Record<string, unknown> | null>(null);
  const [shellTools, setShellTools] = useState(false);
  useEffect(() => { api.getMcpSettings().then(d => { setMcp(d); setShellTools(d.shell_tools_enabled as boolean); }).catch(() => {}); }, []);

  const saveMcp = async () => {
    try { await api.updateMcpSettings({ shell_tools_enabled: shellTools }); alert("MCP 设置已保存"); }
    catch { alert("保存失败"); }
  };

  if (!mcp) return null;
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center gap-2.5">
        <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
          <Server className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h2 className="text-base font-semibold">{t.mcpSettings}</h2>
          <p className="text-xs text-muted-foreground">{t.mcpSettingsDesc}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div><span className="text-muted-foreground">{t.mcpServiceName}:</span> {mcp.service_name as string}</div>
        <div><span className="text-muted-foreground">{t.mcpTransport}:</span> {mcp.transport as string}</div>
        <div><span className="text-muted-foreground">{t.mcpSsePort}:</span> {mcp.sse_port as number}</div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={shellTools} onChange={e => setShellTools(e.target.checked)} className="rounded" />
          <span className="text-muted-foreground">{t.mcpShellTools}</span>
        </label>
      </div>
      <button onClick={saveMcp} className="btn-sm btn-primary">保存 MCP 设置</button>
      <details className="text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Claude Desktop / Cursor 配置</summary>
        <pre className="mt-2 p-3 rounded bg-muted text-[11px] overflow-auto">{`{
  "mcpServers": {
    "AStockPursue": {
      "command": "python",
      "args": ["${mcp.install_cmd || 'agent/mcp_server.py'}"]
    }
  }
}`}</pre>
      </details>
    </div>
  );
}

export function Settings() {
  const { t } = useI18n();
  const user = useAuthStore(s => s.user);
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [dataSettings, setDataSettings] = useState<DataSourceSettings | null>(null);
  const [form, setForm] = useState<LLMFormState | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [tushareToken, setTushareToken] = useState("");
  const [clearTushareToken, setClearTushareToken] = useState(false);
  const [okxApiKey, setOkxApiKey] = useState("");
  const [okxSecretKey, setOkxSecretKey] = useState("");
  const [okxPassphrase, setOkxPassphrase] = useState("");
  const [clearOkx, setClearOkx] = useState(false);
  const [twelvedataApiKey, setTwelvedataApiKey] = useState("");
  const [clearTwelvedata, setClearTwelvedata] = useState(false);
  const [finnhubApiKey, setFinnhubApiKey] = useState("");
  const [clearFinnhub, setClearFinnhub] = useState(false);
  const [tiingoApiKey, setTiingoApiKey] = useState("");
  const [clearTiingo, setClearTiingo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dataSaving, setDataSaving] = useState(false);
  const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.getLLMSettings(), api.getDataSourceSettings()])
      .then(async ([llmData, dataSourceData]) => {
        if (!alive) return;
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
        okx_api_key: okxApiKey.trim() || undefined,
        okx_secret_key: okxSecretKey.trim() || undefined,
        okx_passphrase: okxPassphrase.trim() || undefined,
        clear_okx: clearOkx,
        twelvedata_api_key: twelvedataApiKey.trim() || undefined,
        clear_twelvedata: clearTwelvedata,
        finnhub_api_key: finnhubApiKey.trim() || undefined,
        clear_finnhub: clearFinnhub,
        tiingo_api_key: tiingoApiKey.trim() || undefined,
        clear_tiingo: clearTiingo,
      });
      setDataSettings(updated);
      setTushareToken("");
      setClearTushareToken(false);
      setOkxApiKey("");
      setOkxSecretKey("");
      setOkxPassphrase("");
      setClearOkx(false);
      setTwelvedataApiKey("");
      setClearTwelvedata(false);
      setFinnhubApiKey("");
      setClearFinnhub(false);
      setTiingoApiKey("");
      setClearTiingo(false);
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
      const token = sessionStorage.getItem("vt_token");
      const res = await fetch("/v1/api/auth/change-password", {
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
      const token = sessionStorage.getItem("vt_token");
      const res = await fetch("/v1/api/auth/change-username", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ username: newName }),
      });
      const data = await res.json();
      if (res.ok) {
        setUserMsg("用户名已更新");
        // Update stored user info
        const raw = sessionStorage.getItem("vt_user") || "{}";
        let u: Record<string, unknown> = {};
        try { u = JSON.parse(raw); } catch { /* ignore */ }
        u.username = newName;
        sessionStorage.setItem("vt_user", JSON.stringify(u));
      }
      else setUserMsg(data.detail || "修改失败");
    } catch { setUserMsg("网络错误"); }
    finally { setChangingUser(false); }
  };

  const loggedIn = !!sessionStorage.getItem("vt_token");
  // LLM & data source settings are stored per-user in DB — no manual sync needed

  const accountSection = loggedIn ? (
    <div className="card p-5 space-y-4">
      <div className="flex items-center gap-2.5">
        <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
          <User className="h-4 w-4 text-primary" />
        </div>
        <h2 className="text-base font-semibold">账户设置</h2>
      </div>
      <form onSubmit={changeUsername} className="flex gap-3 items-end">
        <label className="grid gap-1.5 flex-1">
          <span className="text-sm font-medium">用户名</span>
          <input name="new_username" required minLength={2} placeholder={((): string => { try { return JSON.parse(sessionStorage.getItem("vt_user") || "{}").username || ""; } catch { return ""; } })()} className="input" />
        </label>
        <button type="submit" disabled={changingUser} className="btn-sm btn-primary">
          {changingUser ? "..." : "修改"}
        </button>
        {userMsg && <span className={`text-xs ${userMsg.includes("失败") ? "text-danger" : "text-success"}`}>{userMsg}</span>}
      </form>
      <form onSubmit={changePassword} className="flex gap-3 items-end">
        <label className="grid gap-1.5 flex-1">
          <span className="text-sm font-medium">当前密码</span>
          <input name="old_password" type="password" required className="input" />
        </label>
        <label className="grid gap-1.5 flex-1">
          <span className="text-sm font-medium">新密码</span>
          <input name="new_password" type="password" required minLength={4} className="input" />
        </label>
        <button type="submit" disabled={changingPw} className="btn-sm btn-primary">
          {changingPw ? "..." : "修改"}
        </button>
        {pwMsg && <span className={`text-xs ${pwMsg.includes("失败") || pwMsg.includes("错误") ? "text-danger" : "text-success"}`}>{pwMsg}</span>}
      </form>
    </div>
  ) : null;

  if (loading || !form || !settings || !dataSettings) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 p-8">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">{t.settings}</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">{t.settingsDesc}</p>
        </div>
        {accountSection}

        <div className="flex min-h-32 items-center justify-center rounded-xl border bg-card p-8 text-sm text-muted-foreground shadow-sm">
          {settingsLoadError ? (
            <div className="max-w-md text-center space-y-3">
              <div className="font-semibold text-foreground">{t.settingsUnavailable}</div>
              <div className="mt-1">{settingsLoadError}</div>
              <div className="text-xs text-muted-foreground/80">{t.authRequiredHint}</div>
            </div>
          ) : (
            <div className="flex items-center gap-2.5">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span>{t.loading}</span>
            </div>
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
    <div className="mx-auto max-w-5xl space-y-8 p-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">{t.settings}</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">{t.settingsDesc}</p>
      </div>

      {accountSection}

      <div className="space-y-2">
        <h2 className="text-lg font-bold tracking-tight">{t.llmSettings}</h2>
        <p className="max-w-3xl text-sm text-muted-foreground">{t.llmSettingsDesc}</p>
      </div>

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <section className="card p-6">
          <div className="mb-5 flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Server className="h-4 w-4 text-primary" />
            </div>
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
                  className="btn-sm btn-outline shrink-0"
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

        <section className="card p-6">
          <div className="mb-5 flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <SlidersHorizontal className="h-4 w-4 text-primary" />
            </div>
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

            <button
              type="submit"
              disabled={saving}
              className="btn-md btn-primary"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? t.llmSaving : t.llmSaveSettings}
            </button>
          </div>
        </section>
      </form>

      <form onSubmit={submitDataSources} className="card p-6">
        <div className="mb-5 space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Database className="h-4 w-4 text-primary" />
            </div>
            <h2 className="text-base font-semibold">{t.dataSourceSettings}</h2>
          </div>
          <p className="text-sm text-muted-foreground ml-[calc(1.75rem+0.625rem)]">{t.dataSourceSettingsDesc}</p>
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

            {/* OKX credentials */}
            <div className="grid gap-3 rounded-lg border bg-muted/20 p-4">
              <span className="text-sm font-medium">{t.okxApiKey}</span>

              <label className="grid gap-2">
                <span className={labelClass}>{t.okxApiKey}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={okxApiKey}
                    onChange={(event) => setOkxApiKey(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.okx_api_key_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearOkx}
                  />
                </div>
              </label>

              <label className="grid gap-2">
                <span className={labelClass}>{t.okxSecretKey}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={okxSecretKey}
                    onChange={(event) => setOkxSecretKey(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.okx_secret_key_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearOkx}
                  />
                </div>
              </label>

              <label className="grid gap-2">
                <span className={labelClass}>{t.okxPassphrase}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={okxPassphrase}
                    onChange={(event) => setOkxPassphrase(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.okx_passphrase_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearOkx}
                  />
                </div>
              </label>

              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={clearOkx}
                  onChange={(event) => {
                    setClearOkx(event.target.checked);
                    if (event.target.checked) {
                      setOkxApiKey("");
                      setOkxSecretKey("");
                      setOkxPassphrase("");
                    }
                  }}
                  className="h-3.5 w-3.5 accent-primary"
                />
                {t.clearOkx}
              </label>
            </div>

            {/* Paid API Keys */}
            <div className="grid gap-3 rounded-lg border bg-muted/20 p-4">
              <span className="text-sm font-medium">{t.paidApiKeys}</span>

              <label className="grid gap-2">
                <span className={labelClass}>{t.twelvedataApiKey}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={twelvedataApiKey}
                    onChange={(event) => setTwelvedataApiKey(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.twelvedata_api_key_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearTwelvedata}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className={hintClass}>{t.twelvedataApiKeyHint}</span>
                  <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={clearTwelvedata}
                      onChange={(event) => {
                        setClearTwelvedata(event.target.checked);
                        if (event.target.checked) setTwelvedataApiKey("");
                      }}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    {t.clearTwelvedata}
                  </label>
                </div>
              </label>

              <label className="grid gap-2">
                <span className={labelClass}>{t.finnhubApiKey}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={finnhubApiKey}
                    onChange={(event) => setFinnhubApiKey(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.finnhub_api_key_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearFinnhub}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className={hintClass}>{t.finnhubApiKeyHint}</span>
                  <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={clearFinnhub}
                      onChange={(event) => {
                        setClearFinnhub(event.target.checked);
                        if (event.target.checked) setFinnhubApiKey("");
                      }}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    {t.clearFinnhub}
                  </label>
                </div>
              </label>

              <label className="grid gap-2">
                <span className={labelClass}>{t.tiingoApiKey}</span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    value={tiingoApiKey}
                    onChange={(event) => setTiingoApiKey(event.target.value)}
                    className={`${fieldClass} pl-9`}
                    placeholder={dataSettings.tiingo_api_key_configured ? t.okxConfigured : t.okxNotConfigured}
                    autoComplete="off"
                    disabled={clearTiingo}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className={hintClass}>{t.tiingoApiKeyHint}</span>
                  <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={clearTiingo}
                      onChange={(event) => {
                        setClearTiingo(event.target.checked);
                        if (event.target.checked) setTiingoApiKey("");
                      }}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    {t.clearTiingo}
                  </label>
                </div>
              </label>
            </div>

            <button
              type="submit"
              disabled={dataSaving}
              className="btn-md btn-primary"
            >
              {dataSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {dataSaving ? t.llmSaving : t.saveDataSourceSettings}
            </button>
          </div>

          {/* Free data sources */}
          <div className="grid gap-3 rounded-lg border bg-muted/20 p-4">
            <span className="text-sm font-medium">免费数据源</span>
            {([
              ["AKShare", `A股/港股/美股/期货/外汇${dataSettings.akshare_available && dataSettings.akshare_version ? ` v${dataSettings.akshare_version}` : ""}`, dataSettings.akshare_available],
              ["YFinance", "美股 / 港股", dataSettings.yfinance_available],
              ["Tencent", "A股 / 港股", dataSettings.tencent_available],
              ["CCXT", "加密货币 (100+交易所)", dataSettings.ccxt_available],
              ["CoinGecko", "加密货币", dataSettings.coingecko_available],
              ["Futu", "A股 / 港股 (需 FutuOpenD)", dataSettings.futu_available],
              ["Global Indices", "全球指数", dataSettings.global_indices_available],
              ["Commodities", "大宗商品", dataSettings.commodities_available],
            ] as [string, string, boolean][]).map(([name, desc, available]) => (
              <div key={name} className="flex items-center justify-between py-1.5 px-3 rounded-md bg-background/60 border border-border/50">
                <div>
                  <span className="text-sm">{name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{desc}</span>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${available ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}>
                  {available ? "可用" : "不可用"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </form>

      {/* Skill Management */}
      <SkillSection />

      {/* MCP Settings (admin only) */}
      {user?.role === "admin" && <McpSection />}
    </div>
  );
}
