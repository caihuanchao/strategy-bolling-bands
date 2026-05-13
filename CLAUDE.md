# CLAUDE.md

**注意：此文件专门为 Claude Code AI 助手优化，面向人类开发者的完整文档请参考 [README.md](./README.md)。**

---

## 快速索引

| 用途 | 文件路径 |
|------|----------|
| 全局配置（修改参数在此） | `src/config.py` |
| Web 仪表盘 Flask 应用 | `app.py` |
| 一键启动 Web 服务 | `run_server.py` |
| 仪表盘前端模板 | `templates/dashboard.html` |
| 布林带计算 | `src/bollinger.py` |
| MACD/RSI 指标计算 | `src/indicators.py` |
| 技术指标结构化解读 | `src/indicator_interpreter.py` |
| 信号生成和扫描 | `src/signals.py` |
| 数据获取（多源 fallback） | `src/data_fetcher.py` |
| 结果缓存管理 | `src/cache.py` |
| 自选股加载 | `src/watchlist.py` |
| 多周期共振逻辑 | `src/multi_period.py` |
| 回测引擎 | `src/backtest.py` |
| 输出模块（报告/图表） | `src/output.py` |
| 自选股列表 | `watchlist.csv` |
| 原始需求文档 | `idea-000333-bollinger.md` |

---

## 项目目录结构

```
strategy-bolling-bands/
├── app.py                        # Flask Web 应用（API 端点 + 数据加载）
├── run_server.py                 # 一键启动 Web 仪表盘
├── run_workbench.py              # 多标的扫描 + 静态 HTML 生成
├── run_backtest.py               # 单标的回测入口（支持 --phase2）
├── strategy-bolling-bands.py     # 旧版单标脚本（保留对比）
├── watchlist.csv                 # 自选股列表（tab 分隔，symbol+name）
├── requirements.txt              # Python 依赖
├── templates/
│   └── dashboard.html            # Jinja2 仪表盘模板（内联 CSS+JS+Canvas 图表）
├── src/
│   ├── __init__.py
│   ├── config.py                 # Config dataclass：标的/参数/交易成本/多周期/指标配置
│   ├── watchlist.py              # StockInfo dataclass + load_watchlist()
│   ├── data_fetcher.py           # AKShare v1/v2 → BaoStock → 样本数据 fallback
│   ├── bollinger.py              # calculate_bollinger(df, n, m)
│   ├── indicators.py             # calculate_macd(), calculate_rsi()
│   ├── indicator_interpreter.py  # interpret_all(): MACD/RSI/布林带结构化中文解读
│   ├── signals.py                # Signal dataclass + generate_signals() + scan_all_signals()
│   ├── multi_period.py           # 多周期数据对齐和共振确认
│   ├── cache.py                  # CSV/JSON 缓存读写 + metadata.json
│   ├── backtest.py               # Trade/BacktestResult dataclass + 绩效指标
│   └── output.py                 # 控制台报告 + CSV + matplotlib 图表 + 静态 HTML
├── data/
│   ├── cache/
│   │   ├── metadata.json         # 扫描元数据（含参数快照）
│   │   ├── signals.csv           # 缓存的信号列表
│   │   └── bollinger/            # 每只股票一个布林带历史 CSV
│   └── {name}_{symbol}_daily_{date}.csv  # 原始 OHLCV 缓存
├── logs/                         # 回测输出（gitignored）
└── docs/
    ├── ideas/                    # 设计文档
    │   └── adaptive-parameter-lab.md
    └── 技术指标解读案例            # 解读参考案例
```

---

## 核心模块

| 模块 | 路径 | 职责 | 关键类/函数 |
|------|------|------|-------------|
| 配置 | `src/config.py` | dataclass 管理全局参数 | `Config`, `get_config()` |
| Web 应用 | `app.py` | Flask API + 数据加载 + 参数实验室 | `load_data()`, `_background_param_recalc()`, `_compute_market_snapshot()` |
| 布林带 | `src/bollinger.py` | MA20 ± M×SD 计算 | `calculate_bollinger(df, n, m)` |
| 指标 | `src/indicators.py` | MACD(12/26/9) + RSI(14) | `calculate_macd()`, `calculate_rsi()` |
| 指标解读 | `src/indicator_interpreter.py` | MACD/RSI/布林带结构化中文解读 | `interpret_all()`, `interpret_macd()`, `interpret_rsi()`, `interpret_bollinger()` |
| 信号 | `src/signals.py` | 买卖信号生成 + 成交量增强 | `Signal`, `generate_signals()`, `scan_all_signals()`, `scan_latest_signals()` |
| 数据获取 | `src/data_fetcher.py` | 多源 fallback + 增量缓存 | `fetch_batch_data()` |
| 缓存 | `src/cache.py` | 分层 CSV/JSON 缓存 | `load_metadata()`, `save_metadata()`, `load_signals()`, `save_signals()` |
| 自选股 | `src/watchlist.py` | CSV 解析 | `StockInfo`, `load_watchlist()` |
| 多周期 | `src/multi_period.py` | 1h/4h 数据对齐 + 共振确认 | (Phase 2，默认关闭) |
| 回测 | `src/backtest.py` | 模拟交易 + 绩效指标 | `Trade`, `BacktestResult`, `MultiPeriodBacktestResult` |
| 输出 | `src/output.py` | 报告 + CSV + matplotlib 图表 | `save_backtest_report()` |

---

## AI 开发工作流

### 常用命令

```bash
# 启动 Web 仪表盘（推荐，一键交互式访问）
python run_server.py

# 运行单标的回测
python run_backtest.py

# 运行多周期共振回测
python run_backtest.py --phase2

# 生成静态 HTML 仪表盘
python run_workbench.py
```

### 参数实验室 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/params` | 获取当前参数、4 组预设、市场快照 |
| POST | `/api/params/preview` | 提交 `{n, m}`，返回新旧信号计数对比 |
| POST | `/api/params` | 提交 `{n, m}`，后台重算全量信号 |
| POST | `/api/refresh` | 刷新数据 + 重置参数为 config 默认值 |

### 前端 JS 全局状态

| 变量 | 类型 | 用途 |
|------|------|------|
| `signalsData` | object | `/api/signals` 返回的完整响应 |
| `stocksData` | object | `/api/stocks` 返回的完整响应 |
| `pollTimer` | number | `autoRefresh` 每 3 秒轮询的定时器 ID |
| `previewDebounceTimer` | number | 参数预览 300ms 防抖定时器 ID |
| `presetData` | array | 4 组预设模板缓存 |

### 线程安全

- `_data_lock = threading.Lock()` — 保护 `_data_state` 读写
- `_params_lock = threading.Lock()` — 保护 `_current_params` 读写
- `_data_state` 写操作：`load_data()`, `_background_param_recalc()`, `load_cached_data()`
- `_data_state` 读操作：所有 `GET /api/*` 端点

---

## 数据流程

```
watchlist.csv
    ↓ load_watchlist()
StockInfo 列表
    ↓ fetch_batch_data()
原始 OHLCV DataFrame（缓存到 data/*.csv）
    ↓ calculate_bollinger(df, n, m)
    ↓ calculate_macd(df, ...)
    ↓ calculate_rsi(df, ...)
含布林带 + MACD + RSI 列的 DataFrame
    ↓ scan_all_signals()
Signal 列表 + data_dict
    ↓
_data_state = {signals, data_dict, buy_count, sell_count, ...}
    │
    ├──→ GET /api/signals   → 前端统计面板 + 信号表格
    ├──→ GET /api/stocks    → 全部概览表格
    ├──→ GET /api/stock/{s} → 个股详情弹窗（120 条历史 + Canvas 图表 + 指标解读）
    ├──→ GET /api/params    → 参数实验室（预设 + 市场快照 + 滑块）
    └──→ POST /api/params   → _background_param_recalc() → 重算 → 更新 _data_state
```

### 参数实验室重算流程（与 load_data 的区别）

```
load_data()                     _background_param_recalc(n, m)
  网络获取原始 OHLCV              内存中 data_dict 副本
  → 计算布林带 (config 默认参数)   → 仅重算布林带 (新 n, m)
  → 计算 MACD/RSI                 → 重算 MACD/RSI (config 参数不变)
  → 扫描信号                      → 显式 generate_signals() 覆盖旧信号列
  → 更新 _data_state              → scan_all_signals() → 更新 _data_state
```

---

## 引用说明

- 面向人类开发者的完整文档：[README.md](./README.md)
- 参数实验室设计文档：[docs/ideas/adaptive-parameter-lab.md](./docs/ideas/adaptive-parameter-lab.md)
- 项目原始需求：[idea-000333-bollinger.md](./idea-000333-bollinger.md)
