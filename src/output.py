"""输出与日志模块 - 格式化输出回测结果、保存交易记录、绘制图表"""

import os
import pandas as pd
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti TC', 'STHeiti', 'Hiragino Sans GB']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore', message='findfont:')

from .config import get_config, ensure_dirs
from .backtest import BacktestResult, Trade


def print_performance_report(result: BacktestResult):
    """打印绩效报告到控制台"""
    print("\n" + "=" * 60)
    print(f"回测绩效报告 - {get_config().symbol_name}({get_config().symbol})")
    print("=" * 60)
    print(f"初始资金:     ¥{result.initial_capital:,.2f}")
    print(f"最终资金:     ¥{result.final_capital:,.2f}")
    print(f"总收益率:     {result.total_return*100:+.2f}%")
    print(f"年化收益率:   {result.cagr*100:+.2f}%")
    print(f"最大回撤:     {result.max_drawdown*100:.2f}%")
    print("-" * 60)
    print(f"总交易次数:   {result.total_trades}")
    print(f"盈利交易:     {result.winning_trades}")
    print(f"亏损交易:     {result.losing_trades}")
    print(f"胜率:         {result.win_rate*100:.2f}%")
    print(f"盈亏比:       {result.reward_risk_ratio:.2f}")
    print("=" * 60 + "\n")


def save_trades_to_csv(trades: list[Trade], filename: str = "trades.csv"):
    """保存交易记录到 CSV"""
    ensure_dirs()
    config = get_config()
    filepath = os.path.join(config.log_dir, filename)

    data = []
    for t in trades:
        data.append({
            "date": t.date,
            "type": t.type,
            "price": t.price,
            "shares": t.shares,
            "amount": t.amount,
            "commission": t.commission,
            "stamp_duty": t.stamp_duty,
            "total_cost": t.total_cost
        })

    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"交易记录已保存至: {filepath}")


def plot_strategy_chart(result: BacktestResult, filename: str = "strategy_chart.png"):
    """绘制策略图表：价格+布林带+信号点"""
    ensure_dirs()
    config = get_config()
    df = result.df
    filepath = os.path.join(config.log_dir, filename)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=config.plot_figsize, sharex=True, gridspec_kw={'height_ratios': [3, 1]})

    # 子图1：价格、布林带、信号点
    ax1.plot(df["date"], df["close"], label="Close", color="#1f77b4", linewidth=2)
    ax1.plot(df["date"], df["ma_mid"], label="MA20", color="#ff7f0e", linestyle="--")
    ax1.plot(df["date"], df["boll_up"], label="Upper", color="#2ca02c", linestyle=":")
    ax1.plot(df["date"], df["boll_down"], label="Lower", color="#d62728", linestyle=":")
    ax1.fill_between(df["date"], df["boll_up"], df["boll_down"], color="gray", alpha=0.1)

    buy_points = df[df["buy_signal"] == 1]
    ax1.scatter(buy_points["date"], buy_points["close"], marker="^", color="red", s=100, zorder=5, label="Buy")

    sell_points = df[df["sell_signal"] == 1]
    ax1.scatter(sell_points["date"], sell_points["close"], marker="v", color="green", s=100, zorder=5, label="Sell")

    ax1.set_title(f"Bollinger Bands Strategy - {config.symbol_name}({config.symbol})", fontsize=14)
    ax1.set_ylabel("Price", fontsize=12)
    ax1.legend(fontsize=10, loc="upper left")
    ax1.grid(True, alpha=0.3)

    # 子图2：净值曲线
    ax2.plot(df["date"], df["portfolio_value"], label="Portfolio Value", color="#9400d3", linewidth=2)
    ax2.axhline(y=result.initial_capital, color="gray", linestyle="--", alpha=0.5)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.set_ylabel("Portfolio Value", fontsize=12)
    ax2.legend(fontsize=10, loc="upper left")
    ax2.grid(True, alpha=0.3)

    # 调整日期标签
    step = max(1, len(df) // 20)
    ax1.set_xticks(df["date"][::step])
    ax1.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    print(f"策略图表已保存至: {filepath}")
    plt.close()


def save_backtest_report(result: BacktestResult):
    """保存完整回测报告（调用所有输出函数）"""
    print_performance_report(result)
    save_trades_to_csv(result.trades)
    plot_strategy_chart(result)
