# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个**自适应多周期布林带交易工作台**，用于 A 股美的集团(000333)的量化交易策略回测。项目采用渐进式迭代开发：

- **Phase 1 (MVP)**: ✅ 已完成 - 日线级别布林带策略 + 基础回测引擎
- **Phase 2**: ✅ 已完成 - 多周期共振 + MACD/RSI 辅助指标
- **Phase 3**: 自适应参数 + Streamlit Web 仪表盘

## Common Commands

```bash
# 运行 Phase 1 单周期回测
python run_backtest.py

# 运行 Phase 2 多周期共振回测
python run_backtest.py --phase2

# 运行旧版单脚本（保留用于对比）
python strategy-bolling-bands.py
```

## Architecture

### Module Dependencies

```
run_backtest.py (主入口，支持 --phase2 参数)
  └─ src/config.py (配置管理，含多周期和指标配置)
  └─ src/data_fetcher.py → (数据获取: 多源 fallback + 本地缓存，支持 1h/4h 周期)
  └─ src/bollinger.py → (布林带计算)
  └─ src/indicators.py → (MACD/RSI 指标计算)
  └─ src/multi_period.py → (多周期数据对齐和共振逻辑)
  └─ src/signals.py → (信号生成，含多周期共振信号)
  └─ src/backtest.py → (回测引擎: 收益计算 + 绩效指标，支持多周期回测)
  └─ src/output.py → (输出模块: 报告 + CSV + 图表，含多周期对比)
```

### Key Components

- **config.py**: 使用 dataclass 管理策略配置（标的、参数、交易成本、多周期配置、MACD/RSI 参数等）
- **data_fetcher.py**: 统一数据入口，按顺序尝试 AKShare v1/v2 → BaoStock → 本地样本数据，并缓存到 data/ 目录，支持 1h/4h/daily 周期
- **indicators.py** (Phase 2): MACD (12/26/9) 和 RSI (14) 指标计算
- **multi_period.py** (Phase 2): 多周期数据对齐、共振信号检查逻辑
- **bollinger.py**: 布林带计算（MA20 ± 2SD）
- **signals.py**: 信号生成，含多周期共振信号支持
- **backtest.py**: 包含 Trade、BacktestResult、MultiPeriodBacktestResult dataclass，计算总收益率、CAGR、最大回撤、胜率、盈亏比等指标
- **output.py**: 控制台报告 + CSV 交易记录 + matplotlib 图表（含多周期策略对比）

## Important Files

| File | Purpose |
|------|---------|
| `idea-000333-bollinger.md` | 原始需求和路线图 |
| `run_backtest.py` | MVP 主入口，一键运行全流程 |
| `src/config.py` | 全局配置，修改参数请在此处 |
| `src/data_fetcher.py` | 数据源扩展在此添加 |

## Data Flow

1. `get_stock_data()` → 获取并缓存 OHLCV 数据
2. `calculate_bollinger()` → 计算 MA20、上下轨
3. `generate_signals()` → 生成买卖信号（跌破下轨买，突破上轨卖）
4. `run_backtest()` → 模拟交易，计算净值
5. `save_backtest_report()` → 输出结果

## Directories

- `src/`: 模块化代码
- `data/`: 缓存数据（gitignored）
- `logs/`: 回测输出（gitignored）
