# Settings Page Redesign

**Date:** 2026-06-21
**Status:** Draft

## 1. Current Situation

Current settings page has only **4 fields** (language, theme preset, default market, notifications toggle), while the backend supports **12+ settings** across Go `UserSettings` + Python `vt_users` columns. Additionally:

- Go `SettingsHandler` uses **in-memory map** — settings lost on restart
- Frontend `Settings` interface doesn't match Go `UserSettings` struct
- Backend has 3 separate settings domains (Go handler, Python user_config, local Zustand) with no sync
- No i18n keys for settings form labels (hardcoded English strings)
- Broker credentials, LLM config, data sources all exist in DB but have no UI

## 2. Goals

- Single unified settings page with **tabbed sections** covering all user-configurable domains
- Persist settings to DB (via Go API → PG)
- Add API endpoints for settings domains that lack them
- Full i18n support (en/zh)

## 3. Settings Groups

### Tab 1: General (通用)

| Field | Type | Backend Key | Default | Notes |
|-------|------|-------------|---------|-------|
| Language | `select` | `language` | `"en"` | en/zh |
| Theme Preset | `select` | `theme` | `"compact"` | compact/standard |
| Default Market | `select` | `default_market` | `"cn"` | cn/hk/us/crypto |
| Default Frequency | `select` | `default_freq` | `"1d"` | 1m/5m/15m/30m/1h/4h/1d/1w |
| Default Symbols | `tags-input` | `default_symbols` | `["000300.SH"]` | comma-separated watchlist |

### Tab 2: Risk Limits (风控)

| Field | Type | Backend Key | Default | Notes |
|-------|------|-------------|---------|-------|
| Max Position % | `number` | `risk_limits.max_position_pct` | `20` | 0-100% slider + input |
| Stop Loss % | `number` | `risk_limits.stop_loss_pct` | `5` | per-position |
| Take Profit % | `number` | `risk_limits.take_profit_pct` | `10` | per-position |
| Trailing Stop % | `number` | `risk_limits.trailing_stop_pct` | `0` | 0 = disabled |
| Daily Loss Limit | `number` | `risk_limits.daily_loss_limit` | `10000` | currency |
| Max Position Count | `number` | `risk_limits.max_position_count` | `10` | max concurrent positions |

### Tab 3: Data Sources (数据源)

API keys for market data providers (masked display, reveal on hover/click).

| Field | Type | Backend Key | Notes |
|-------|------|-------------|-------|
| Tushare Token | `password` | `data_sources.tushare` | |
| Twelve Data API Key | `password` | `data_sources.twelvedata` | |
| Finnhub API Key | `password` | `data_sources.finnhub` | |
| Tiingo API Key | `password` | `data_sources.tiingo` | |

Each field shows `••••••••` with a small eye toggle to reveal. "Test Connection" button per provider.

### Tab 4: LLM (AI 模型)

| Field | Type | Backend Key | Default | Notes |
|-------|------|-------------|---------|-------|
| Provider | `select` | `llm.provider` | `"openai"` | openai/azure/anthropic/local |
| Model | `select` | `llm.model` | `"gpt-4o-mini"` | depends on provider |
| API Key | `password` | `llm.api_key` | | masked |
| Base URL | `text` | `llm.base_url` | `""` | for proxy/local |

"Test Connection" button that sends a simple prompt and reports latency.

### Tab 5: Brokers (经纪商)

Broker credentials management table. Each row: exchange, label (user-defined nickname), API key / secret / passphrase (masked), testnet toggle, active toggle.

| Field | Type | Notes |
|-------|------|-------|
| Exchange | `select` | binance/okx/futu (from `/api/v1/broker/list`) |
| Label | `text` | user-defined name |
| API Key | `password` | |
| Secret Key | `password` | |
| Passphrase | `password` | OKX only, conditionally shown |
| Testnet | `toggle` | default true |
| Active | `toggle` | default true |

API: `GET/POST/PUT/DELETE /api/v1/broker/credentials` (new endpoints needed, backed by `broker_credentials` table)

"Test Connection" button per row that pings the exchange.

### Tab 6: Notifications (通知)

| Field | Type | Notes |
|-------|------|-------|
| Notifications Enabled | `toggle` | master switch |
| Telegram Bot Token | `password` | |
| Telegram Chat ID | `text` | |
| Email SMTP Host | `text` | |
| Email SMTP Port | `number` | |
| Email Username | `text` | |
| Email Password | `password` | |
| Email From | `text` | |
| Webhook URL | `text` | for custom webhook |
| Alert on Error | `toggle` | default true |
| Alert on Trade | `toggle` | default false |
| Daily Summary | `toggle` | default false |

Each notification channel has "Test" button.

### Tab 7: Account (账户)

| Field | Type | Notes |
|-------|------|-------|
| Username | `text` | read-only display |
| Email | `text` | editable |
| Change Password | section | current / new / confirm |

## 4. Backend Changes Required

### 4a. Go API — Settings Persistence

Create `user_settings` table in PG:

```sql
CREATE TABLE user_settings (
    user_id     INTEGER PRIMARY KEY REFERENCES vt_users(id),
    settings    JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

Refactor `SettingsHandler` to read/write PG instead of in-memory map. The JSONB schema matches the frontend settings groups.

### 4b. Go API — New Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/broker/credentials` | List user's broker credentials |
| `POST` | `/api/v1/broker/credentials` | Create credential |
| `PUT` | `/api/v1/broker/credentials/:id` | Update credential |
| `DELETE` | `/api/v1/broker/credentials/:id` | Delete credential |
| `POST` | `/api/v1/broker/credentials/:id/test` | Test connection |
| `POST` | `/api/v1/data-sources/test` | Test a data source API key |
| `POST` | `/api/v1/llm/test` | Test LLM connection |
| `POST` | `/api/v1/notifications/test-telegram` | Test Telegram |
| `POST` | `/api/v1/notifications/test-email` | Test email |
| `POST` | `/api/v1/notifications/test-webhook` | Test webhook |
| `PUT` | `/api/v1/auth/password` | Change password |
| `PUT` | `/api/v1/auth/email` | Update email |

### 4c. Go API — Settings Schema (full JSONB)

```json
{
  "general": {
    "language": "en",
    "theme": "compact",
    "default_market": "cn",
    "default_freq": "1d",
    "default_symbols": ["000300.SH"]
  },
  "risk_limits": {
    "max_position_pct": 20,
    "stop_loss_pct": 5,
    "take_profit_pct": 10,
    "trailing_stop_pct": 0,
    "daily_loss_limit": 10000,
    "max_position_count": 10
  },
  "data_sources": {
    "tushare": "encrypted",
    "twelvedata": "encrypted",
    "finnhub": "encrypted",
    "tiingo": "encrypted"
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "api_key": "encrypted",
    "base_url": ""
  },
  "notifications": {
    "enabled": true,
    "telegram_bot_token": "encrypted",
    "telegram_chat_id": "",
    "email_smtp_host": "",
    "email_smtp_port": 587,
    "email_username": "",
    "email_password": "encrypted",
    "email_from": "",
    "webhook_url": "",
    "alert_on_error": true,
    "alert_on_trade": false,
    "daily_summary": false
  },
  "account": {
    "email": ""
  }
}
```

Sensitive fields (`api_key`, `secret`, `password`, `token`) are AES-256-GCM encrypted at rest (consistent with existing `user_config.py` pattern).

### 4d. Broker Credentials — Reuse Existing Table

The `broker_credentials` table in PG already exists. Add Go endpoints to CRUD it (currently only Python uses it).

## 5. Frontend Component Tree

```
SettingsPage (tabs layout)
├── GeneralTab
│   ├── LanguageSelect
│   ├── ThemeSelect
│   ├── DefaultMarketSelect
│   ├── DefaultFreqSelect
│   └── DefaultSymbolsInput (tags)
├── RiskTab
│   ├── MaxPositionPctSlider
│   ├── StopLossPctInput
│   ├── TakeProfitPctInput
│   ├── TrailingStopPctInput
│   ├── DailyLossLimitInput
│   └── MaxPositionCountInput
├── DataSourcesTab
│   ├── ApiKeyField (tushare)
│   ├── ApiKeyField (twelvedata)
│   ├── ApiKeyField (finnhub)
│   ├── ApiKeyField (tiingo)
│   └── TestConnectionButton (per row)
├── LLMTab
│   ├── ProviderSelect
│   ├── ModelSelect (dynamic based on provider)
│   ├── ApiKeyField
│   ├── BaseUrlInput
│   └── TestConnectionButton
├── BrokersTab
│   ├── CredentialsTable
│   │   ├── CredentialRow (exchange, label, key, testnet, active, actions)
│   │   └── AddCredentialButton
│   └── CredentialFormDialog
├── NotificationsTab
│   ├── EnabledToggle (master)
│   ├── TelegramConfig (bot token + chat id + test)
│   ├── EmailConfig (smtp host, port, user, pass, from + test)
│   ├── WebhookUrlInput + test
│   └── AlertToggles (error, trade, daily summary)
└── AccountTab
    ├── UsernameDisplay (read-only)
    ├── EmailInput + save
    ├── ChangePasswordSection
    │   ├── CurrentPasswordInput
    │   ├── NewPasswordInput
    │   └── ConfirmPasswordInput
    └── SaveButton
```

## 6. i18n Keys

Add `settings.*` namespace to `en.json` and `zh.json`:

```
settings.title
settings.general
settings.riskLimits
settings.dataSources
settings.llm
settings.brokers
settings.notifications
settings.account
settings.language
settings.theme
settings.defaultMarket
settings.defaultFreq
settings.defaultSymbols
settings.maxPositionPct
settings.stopLossPct
settings.takeProfitPct
settings.trailingStopPct
settings.dailyLossLimit
settings.maxPositionCount
settings.tushareToken
settings.twelvedataKey
settings.finnhubKey
settings.tiingoKey
settings.llmProvider
settings.llmModel
settings.llmApiKey
settings.llmBaseUrl
settings.brokerExchange
settings.brokerLabel
settings.brokerApiKey
settings.brokerSecret
settings.brokerPassphrase
settings.brokerTestnet
settings.brokerActive
settings.addCredential
settings.testConnection
settings.testSuccess
settings.testFailed
settings.notificationsEnabled
settings.telegramBotToken
settings.telegramChatId
settings.emailSmtpHost
settings.emailSmtpPort
settings.emailUsername
settings.emailPassword
settings.emailFrom
settings.webhookUrl
settings.alertOnError
settings.alertOnTrade
settings.dailySummary
settings.username
settings.email
settings.changePassword
settings.currentPassword
settings.newPassword
settings.confirmPassword
settings.passwordChanged
settings.settingsSaved
settings.resetToDefaults
```

## 7. Wireframe Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Settings                                                    │
│                                                              │
│  ┌─General──Risk──Data Sources──LLM──Brokers──Notifications──Account─┐
│  │                                                                    │
│  │  Language        ┌──────────────────────────────────────┐         │
│  │                  │ English                       ▼      │         │
│  │                  └──────────────────────────────────────┘         │
│  │                                                                    │
│  │  Theme Preset    ┌──────────────────────────────────────┐         │
│  │                  │ Compact                       ▼      │         │
│  │                  └──────────────────────────────────────┘         │
│  │                                                                    │
│  │  Default Market  ┌──────────────────────────────────────┐         │
│  │                  │ China A-Share                  ▼      │         │
│  │                  └──────────────────────────────────────┘         │
│  │                                                                    │
│  │  Default Freq    ┌──────────────────────────────────────┐         │
│  │                  │ 1d                                 ▼ │         │
│  │                  └──────────────────────────────────────┘         │
│  │                                                                    │
│  │  Default Symbols ┌──────────────────────────────────────┐         │
│  │                  │ 000300.SH ×   600519.SH ×            │         │
│  │                  └──────────────────────────────────────┘         │
│  │                                                                    │
│  │  ┌──────────────────────────────────────────────────────────────┐ │
│  │  │                    [Save Settings]    [Reset to Defaults]    │ │
│  │  └──────────────────────────────────────────────────────────────┘ │
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

## 8. Implementation Order

1. **Phase 1** — General + Risk + Account tabs (simple form fields, reuse existing Go `UserSettings`)
   - Add `user_settings` PG table
   - Refactor Go `SettingsHandler` to use PG
   - Expand frontend settings form
   - Add i18n keys

2. **Phase 2** — Data Sources + LLM tabs (sensitive fields, test connection)
   - Add test connection endpoints in Go
   - Implement masked password fields + reveal
   - Wire to Python test logic

3. **Phase 3** — Brokers tab (CRUD table, test connection)
   - Add Go CRUD endpoints for `broker_credentials` table
   - Table UI with add/edit/delete dialogs
   - Test connection per row

4. **Phase 4** — Notifications tab (multi-channel, test)
   - Add notification channel config endpoints
   - Test buttons for each channel
   - Alert preference toggles

## 9. Edge Cases

- **Empty state**: No brokers configured → "Add your first broker" empty state with illustration
- **Loading state**: Skeleton per tab during fetch
- **Error state**: Per-field validation errors (not just global)
- **Partial save**: Each tab saves independently (not whole form) — avoid losing all unsaved changes
- **Sensitive field handling**: API never returns actual keys in plaintext; client only sees `••••••••` or last 4 chars
- **Test connection timeout**: 10s timeout with spinner, show latency on success
- **Password change**: Force re-login after password change (invalidate JWT)
