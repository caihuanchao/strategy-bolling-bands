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
| MACD/RSI/KDJ/ATR 指标计算 | `src/indicators.py` |
| 技术指标结构化解读 | `src/indicator_interpreter.py` |
| 布林带策略实现 | `src/strategies/bollinger.py` |
| 双均线策略实现 | `src/strategies/dual_ma.py` |
| 双均线策略解读 | `src/strategies/dual_ma_interpreter.py` |
| 成交量分析策略实现 | `src/strategies/volume.py` |
| 成交量分析策略解读 | `src/strategies/volume_interpreter.py` |
| 三重确认策略实现 | `src/strategies/triple_confirm.py` |
| 三重确认策略解读 | `src/strategies/triple_confirm_interpreter.py` |
| KDJ+BB+ATR 策略实现 | `src/strategies/kdj_bollinger_atr.py` |
| KDJ+BB+ATR 策略解读 | `src/strategies/kdj_bollinger_atr_interpreter.py` |
| 策略注册中心 | `src/strategies/__init__.py` |
| 信号生成和扫描 | `src/signals.py` |
| 数据获取（多源 fallback） | `src/data_fetcher.py` |
| 结果缓存管理 | `src/cache.py` |
| 自选股加载 | `src/watchlist.py` |
| 多周期共振逻辑 | `src/multi_period.py` |
| 回测引擎 | `src/backtest.py` |
| 输出模块（报告/图表） | `src/output.py` |
| 自选股列表 | `watchlist.csv` |

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
│   ├── indicators.py             # calculate_macd(), calculate_rsi(), calculate_kdj(), calculate_atr()
│   ├── indicator_interpreter.py  # interpret_all(): MACD/RSI/布林带结构化中文解读
│   ├── signals.py                # Signal dataclass + generate_signals() + scan_all_signals()
│   ├── strategies/               # 策略系统（5 策略 + 4 解读器）
│   │   ├── __init__.py                        # StrategyBase ABC + StrategyRegistry 单例
│   │   ├── bollinger.py                       # BollingerStrategy（布林带触碰）
│   │   ├── dual_ma.py                         # DualMAStrategy（双均线交叉）
│   │   ├── dual_ma_interpreter.py             # interpret_dual_ma_all(): 双均线结构化中文解读
│   │   ├── volume.py                          # VolumeAnalysisStrategy（成交量分析）
│   │   ├── volume_interpreter.py              # interpret_volume_all(): 成交量分析 7 维解读
│   │   ├── triple_confirm.py                  # TripleConfirmStrategy（三重确认）
│   │   ├── triple_confirm_interpreter.py      # interpret_triple_confirm_all(): 三重确认 7 维解读
│   │   ├── kdj_bollinger_atr.py               # KdjBollingerAtrStrategy（KDJ+BB+ATR）
│   │   └── kdj_bollinger_atr_interpreter.py   # interpret_kdj_bb_atr_all(): KDJ+BB+ATR 7 维解读
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
| 指标 | `src/indicators.py` | MACD(12/26/9) + RSI(14) + KDJ(9,3,3) + ATR(14) | `calculate_macd()`, `calculate_rsi()`, `calculate_kdj()`, `calculate_atr()`, `calculate_adx()` |
| 指标解读 | `src/indicator_interpreter.py` | MACD/RSI/布林带结构化中文解读 | `interpret_all()`, `interpret_macd()`, `interpret_rsi()`, `interpret_bollinger()` |
| 策略系统 | `src/strategies/__init__.py` | 策略 ABC + 注册中心（单例） | `StrategyBase`, `StrategyRegistry` |
| 布林带策略 | `src/strategies/bollinger.py` | 布林带触碰策略实现 | `BollingerStrategy.generate_signals()`, `create_signal()` |
| 双均线策略 | `src/strategies/dual_ma.py` | 双均线交叉策略实现（EMA 金叉/死叉） | `DualMAStrategy.generate_signals()`, `create_signal()` |
| 双均线解读 | `src/strategies/dual_ma_interpreter.py` | 双均线策略结构化中文解读 | `interpret_dual_ma_all()` → 交叉信号/趋势/可靠性/成交量/操作建议 |
| 成交量策略 | `src/strategies/volume.py` | 成交量分析策略（OBV+背离+形态） | `VolumeAnalysisStrategy.generate_signals()`, `create_signal()` |
| 成交量解读 | `src/strategies/volume_interpreter.py` | 成交量分析 7 维解读 | `interpret_volume_all()` → 量价关系/背离/突破/回调/OBV/形态/建议 |
| 三重确认策略 | `src/strategies/triple_confirm.py` | MACD+RSI+成交量+ADX 四指标共振 | `TripleConfirmStrategy.generate_signals()`, `create_signal()` |
| 三重确认解读 | `src/strategies/triple_confirm_interpreter.py` | 三重确认 7 维解读 | `interpret_triple_confirm_all()` → 信号等级/MACD/RSI/成交量/辅助/出场/建议 |
| KDJ+BB+ATR 策略 | `src/strategies/kdj_bollinger_atr.py` | 三环境自适应系统 | `KdjBollingerAtrStrategy.generate_signals()`, `create_signal()` |
| KDJ+BB+ATR 解读 | `src/strategies/kdj_bollinger_atr_interpreter.py` | KDJ+BB+ATR 7 维解读 | `interpret_kdj_bb_atr_all()` → 环境/信号等级/KDJ/布林带/ATR/出场/建议 |
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

### 策略切换 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/strategies` | 获取所有可用策略列表 |
| POST | `/api/strategy/switch` | 提交 `{"strategy": "dual_ma"}`, 后台重算全量信号 |

### 前端 JS 全局状态

| 变量 | 类型 | 用途 |
|------|------|------|
| `currentStrategyId` | string | 当前活跃策略 ID (`"bollinger"` / `"dual_ma"` / `"volume_analysis"` / `"triple_confirm"` / `"kdj_bollinger_atr"`) |
| `strategiesList` | array | `/api/strategies` 返回的策略列表缓存 |
| `signalsData` | object | `/api/signals` 返回的完整响应 |
| `stocksData` | object | `/api/stocks` 返回的完整响应 |
| `pollTimer` | number | `autoRefresh` 每 3 秒轮询的定时器 ID |
| `previewDebounceTimer` | number | 参数预览 300ms 防抖定时器 ID |
| `presetData` | array | 策略预设模板缓存（动态按策略加载） |

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
    ↓ calculate_kdj(df, ...)         # 策略专属按需计算
    ↓ calculate_atr(df, ...)         # 策略专属按需计算
    ↓ calculate_adx(df, ...)         # 策略专属按需计算
含布林带 + MACD + RSI + KDJ + ATR 列的 DataFrame
    ↓ _scan_with_strategy(df, strategy, params)
    │ (strategy.generate_signals() → buy_signal, sell_signal, [策略专属列]...)
Signal 列表 + data_dict
    ↓
_data_state = {signals, data_dict, buy_count, sell_count, ...}
    │
    ├──→ GET /api/signals   → 前端统计面板 + 信号表格
    ├──→ GET /api/stocks    → 全部概览表格
    ├──→ GET /api/stock/{s} → 个股详情弹窗（120 条历史 + Canvas 图表 + 策略感知解读）
    │                           ├── 通用层: interpret_all() (MACD/RSI/布林带) 始终执行
    │                           └── 策略专属层: 按 DataFrame 列存在性自动分发
    │                               ├── dual_ma: interpret_dual_ma_all()
    │                               ├── volume_analysis: interpret_volume_all()
    │                               ├── triple_confirm: interpret_triple_confirm_all()
    │                               └── kdj_bollinger_atr: interpret_kdj_bb_atr_all()
    ├──→ GET /api/params    → 参数实验室（策略专属预设 + 市场快照 + 滑块）
    ├──→ POST /api/params   → _background_param_recalc() → 重算 → 更新 _data_state
    └──→ POST /api/strategy/switch → 切换策略 → _background_param_recalc() → 全量重算
```

### 参数实验室重算流程（与 load_data 的区别）

```
load_data()                     _background_param_recalc(new_params)
  网络获取原始 OHLCV              内存中 data_dict 副本
  → 计算布林带 (config 默认)      → 仅重算当前策略所需指标 (新参数)
  → 计算 MACD/RSI/KDJ/ATR         → 显式 generate_signals() 覆盖旧信号列
  → 扫描信号                      → scan_all_signals() → 更新 _data_state
  → 更新 _data_state
```

---

## 引用说明

- 面向人类开发者的完整文档：[README.md](./README.md)
- 参数实验室设计文档：[docs/ideas/adaptive-parameter-lab.md](./docs/ideas/adaptive-parameter-lab.md)
