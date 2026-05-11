# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个**自适应多周期布林带交易工作台**，用于 A 股美的集团(000333)的量化交易策略回测。项目采用渐进式迭代开发：

- **Phase 1 (MVP)**: ✅ 已完成 - 日线级别布林带策略 + 基础回测引擎
- **Phase 2**: 多周期共振 + MACD/RSI 辅助指标
- **Phase 3**: 自适应参数 + Streamlit Web 仪表盘

## Common Commands

```bash
# 运行完整回测
python run_backtest.py

# 运行旧版单脚本（保留用于对比）
python strategy-bolling-bands.py
```

## Architecture

### Module Dependencies

```
run_backtest.py (主入口)
  └─ src/config.py (配置管理)
  └─ src/data_fetcher.py → (数据获取: 多源 fallback + 本地缓存)
  └─ src/bollinger.py → (布林带计算)
  └─ src/signals.py → (信号生成)
  └─ src/backtest.py → (回测引擎: 收益计算 + 绩效指标)
  └─ src/output.py → (输出模块: 报告 + CSV + 图表)
```

### Key Components

- **config.py**: 使用 dataclass 管理策略配置（标的、参数、交易成本等）
- **data_fetcher.py**: 统一数据入口，按顺序尝试 AKShare v1/v2 → BaoStock → 本地样本数据，并缓存到 data/ 目录
- **backtest.py**: 包含 Trade 和 BacktestResult dataclass，计算总收益率、CAGR、最大回撤、胜率、盈亏比等指标
- **output.py**: 控制台报告 + CSV 交易记录 + matplotlib 双图（价格/布林带/信号 + 净值曲线）

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
