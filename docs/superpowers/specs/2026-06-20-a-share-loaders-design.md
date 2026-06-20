# A 股数据加载器扩展设计

> 日期：2026-06-20 | 状态：已确认

## 1. 背景

A 股 8 源回退链目前仅有 2 个加载器（腾讯 P5、东方财富 P10），缺口 6 个。本次补齐 3 个 HTTP
原生加载器，将可用数据源扩展到 5 个。mootdx 通过 Python gRPC 代理实现（后续），Tushare
和 Futu 需要额外认证配置（再后续）。

## 2. 设计

### 2.1 模式

所有加载器遵循 `services/go/internal/market/loader/eastmoney.go` 建立的统一模式：

- `init()` 自注册，带优先级
- 实现 `Loader` 接口：`Name()`, `IsAvailable()`, `FetchBars()`
- 测试使用 `httptest.NewServer` 模拟外部 API
- 不修改任何已有文件

### 2.2 新增加载器

| 文件 | 加载器 | 优先级 | 类型 | API Key |
|------|--------|--------|------|---------|
| `sina.go` | 新浪财经 | 1 | 实时快照（文本格式） | 不需要 |
| `baidu.go` | 百度财经 | 6 | 历史日线（JSON） | 不需要 |
| `twelvedata.go` | TwelveData | 7 | 历史日线（JSON，值全是字符串） | 可选（环境变量） |

### 2.3 最终回退链

```
Sina(P1) → Tencent(P5) → Baidu(P6) → TwelveData(P7) → EastMoney(P10)
```

### 2.4 A 股交易所代码映射

| 前缀 | 交易所 | Sina | Baidu | TwelveData |
|------|--------|------|-------|------------|
| 6 | 上海 | `sh{code}` | `sh.{code}` | `{code}.SHH` |
| 0/3 | 深圳 | `sz{code}` | `sz.{code}` | `{code}.SHZ` |
| 4/8/9 | 北京 | `bj{code}` | `bj.{code}` | `{code}.BJS` |

## 3. 加载器详述

### 3.1 新浪 Sina（优先级 1）

- **URL**: `http://hq.sinajs.cn/list=sh600000`
- **必带请求头**: `Referer: http://finance.sina.com.cn`（否则 403）
- **返回格式**（文本，非 JSON）:
  ```
  var hq_str_sh600000="名称,开盘,昨收,现价,最高,最低,...,成交量,...,日期,时间"
  ```
- **字段索引**: Open=[1], Close=[3], High=[4], Low=[5], Volume=[8], Date=[30]
- **历史数据**: 不支持。传入非零 start/end 返回错误（与腾讯模式一致）
- **编码**: GBK — 股票名称是中文，但只需提取数字字段，UTF-8 截取数字部分不受影响

### 3.2 百度 Baidu（优先级 6）

- **URL**: `https://finance.pc22333.com/finance/stock/history?code=sh.600000&start_date=2026-01-01&end_date=2026-06-20`
- **返回格式**（JSON）:
  ```json
  {"status": 0, "data": [{"date": "...", "open": 10.0, "close": 10.5, "high": 11.0, "low": 9.5, "volume": 1000000}]}
  ```
- **无需认证**，免费访问
- **日期过滤**: 通过 URL 查询参数传入 `start_date`/`end_date`

### 3.3 TwelveData（优先级 7）

- **URL**: `https://api.twelvedata.com/time_series?symbol=600000.SHH&interval=1day&apikey={KEY}`
- **返回格式**（JSON，所有 OHLCV 值都是字符串）:
  ```json
  {"status": "ok", "values": [{"datetime": "...", "open": "10.00", "high": "11.00", "low": "9.50", "close": "10.50", "volume": "1000000"}]}
  ```
- **API Key**: 通过 `os.Getenv("TWELVEDATA_API_KEY")` 读取，为空也可用（速率限制低：~8次/分钟）
- **速率超限**: 返回 HTTP 429 → 加载器返回 error → DataStore 自动回退到 EastMoney
- **值解析**: 所有字段必须用 `strconv.ParseFloat`/`strconv.ParseInt` 从字符串转换

## 4. 测试策略

每个加载器一个测试文件，使用 `httptest.NewServer` 返回静态 mock 数据：

- **Sina 测试**: mock 返回单行文本格式数据，验证 Name/IsAvailable/FetchBars，验证传入历史日期范围返回 error
- **Baidu 测试**: mock 返回单条 JSON K线，验证字段解析正确
- **TwelveData 测试**: mock 返回字符串格式 JSON，验证字符串→数值转换正确

## 5. 文件清单

全部在 `services/go/internal/market/loader/`：

**新建（6 个）**:
- `sina.go` / `sina_test.go`（~90 + ~45 行）
- `baidu.go` / `baidu_test.go`（~100 + ~45 行）
- `twelvedata.go` / `twelvedata_test.go`（~110 + ~45 行）

**不修改任何已有文件**——加载器通过 `init()` 自注册。

## 6. 验证

```bash
cd services/go
go test ./internal/market/loader/ -v -count=1 -run "TestSina|TestBaidu|TestTwelveData"
go test ./... -count=1 -short    # 确认 168 个已有测试不受影响
go build ./...                    # 确认编译通过
```
