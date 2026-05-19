#!/usr/bin/env python
"""周线 RSI 策略独立回测脚本 — 标的: 513910 港股通央企红利ETF华夏"""

import sys
import os
import csv
import pandas as pd
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtest import run_backtest_with_strategy, backtest_result_to_dict
from src.strategies.weekly_rsi import WeeklyRsiStrategy
from src.output import print_performance_report

SYMBOL = "513910"
NAME = "港股通央企红利ETF华夏"
INITIAL_CAPITAL = 100_000
LOT_SIZE = 100  # A股ETF
CACHE_FILE = "data/港股通央企红利ETF华夏_513910_daily_20250101.csv"

# 回测参数
PARAMS = {
    "rsi_period": 6,
    "rsi_oversold": 50,
    "rsi_overbought": 60,
    "divergence_lookback": 20,
}


def save_trades_csv(trades, symbol):
    """保存交易明细到 logs/ 目录"""
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"logs/{symbol}_weekly_rsi_trades_{timestamp}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "type", "shares", "price", "amount", "commission", "reason"])
        w.writeheader()
        for t in trades:
            w.writerow({
                "date": str(t.date),
                "type": t.type,
                "shares": t.shares,
                "price": round(t.price, 4),
                "amount": round(t.amount, 2),
                "commission": round(t.commission, 4),
                "reason": getattr(t, "reason", ""),
            })
    return path


def main():
    print("=" * 60)
    print("周线 RSI 策略回测")
    print("=" * 60)

    strategy = WeeklyRsiStrategy()
    params = PARAMS

    print(f"标的: {NAME}({SYMBOL})")
    print(f"策略: {strategy.strategy_name}")
    print(f"参数: {params}")
    print(f"初始资金: ¥{INITIAL_CAPITAL:,.0f}")
    print()

    print("从本地缓存加载数据...")
    if not os.path.exists(CACHE_FILE):
        print(f"错误: 缓存文件不存在: {CACHE_FILE}")
        return 1
    df = pd.read_csv(CACHE_FILE)

    if df is None or len(df) < 60:
        print("错误: 数据不足，至少需要 60 个交易日（~3个月）")
        return 1

    print(f"数据范围: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]} ({len(df)} 条)")
    print()

    # 生成信号并展示周线 RSI 概况
    df_sig = strategy.generate_signals(df, params)
    weekly_data = df_sig[df_sig["weekly_rsi"].notna()]
    if len(weekly_data) > 0:
        print("周线 RSI 概况:")
        print(f"  周线数据点数: {len(weekly_data)}")
        print(f"  RSI 最低: {weekly_data['weekly_rsi'].min():.1f}")
        print(f"  RSI 最高: {weekly_data['weekly_rsi'].max():.1f}")
        print(f"  RSI 当前: {weekly_data['weekly_rsi'].iloc[-1]:.1f}")
        print(f"  买入信号数: {int(df_sig['buy_signal'].sum())}")
        print(f"  卖出信号数: {int(df_sig['sell_signal'].sum())}")
        print()

        # 最近 8 周 RSI
        print("最近 8 周 RSI:")
        recent = weekly_data.tail(8)
        for _, row in recent.iterrows():
            rsi = row["weekly_rsi"]
            buy = " [买入]" if row.get("buy_signal") == 1 else ""
            sell = " [卖出]" if row.get("sell_signal") == 1 else ""
            zone = "超卖" if rsi <= 35 else "超买" if rsi >= 65 else "中性" if 45 <= rsi <= 55 else "偏弱" if rsi < 45 else "偏强"
            print(f"  {str(row['date'])[:10]}  RSI={rsi:5.1f}  close={row['close']:.3f}  {zone}{buy}{sell}")
        print()

    print("运行回测...")
    result = run_backtest_with_strategy(
        df, strategy, params,
        initial_capital=INITIAL_CAPITAL,
        lot_size=LOT_SIZE,
    )

    print()
    print_performance_report(result, symbol=SYMBOL, name=NAME)

    if result.trades:
        path = save_trades_csv(result.trades, SYMBOL)
        print(f"交易记录已保存至: {path}")

        print("\n交易明细:")
        print(f"{'日期':<12} {'方向':<4} {'股数':>6} {'价格':>8} {'金额':>12} {'手续费':>6}")
        print("-" * 56)
        for t in result.trades:
            print(f"{str(t.date):<12} {t.type:<4} {t.shares:>6} {t.price:>8.2f} {t.amount:>12.0f} {t.commission:>6.2f}")
    else:
        print("\n无交易产生。该标在回测期内未触发周线 RSI 买入条件。")
        print("（买入条件要求：RSI < 35 后反弹 + 底背离确认）")

    print("\n" + "=" * 60)
    print("回测完成！")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
