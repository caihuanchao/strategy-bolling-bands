"""回测引擎 - 计算策略收益和绩效指标"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .config import get_config


@dataclass
class Trade:
    """单条交易记录"""
    date: str
    type: str  # "buy" or "sell"
    price: float
    shares: int
    amount: float
    commission: float
    stamp_duty: float
    total_cost: float


@dataclass
class BacktestResult:
    """回测结果"""
    df: pd.DataFrame
    trades: List[Trade]
    portfolio_values: pd.Series
    initial_capital: float
    final_capital: float
    total_return: float
    cagr: float
    max_drawdown: float
    win_rate: float
    reward_risk_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_days: float = 0.0
    sharpe_ratio: float = 0.0


def run_backtest(
    df: pd.DataFrame,
    initial_capital: Optional[float] = None
) -> BacktestResult:
    """
    运行回测

    Args:
        df: 包含价格和信号的 DataFrame
        initial_capital: 初始资金，默认使用配置

    Returns:
        BacktestResult 对象，包含完整回测结果
    """
    config = get_config()
    initial_capital = initial_capital or config.initial_capital

    df = df.copy().reset_index(drop=True)
    cash = initial_capital
    shares_held = 0
    portfolio_values = []
    trades = []

    for i, row in df.iterrows():
        current_price = row["close"]
        buy_signal = row["buy_signal"]
        sell_signal = row["sell_signal"]

        # 执行买入
        if buy_signal == 1 and shares_held == 0 and cash > 0:
            if config.position_size_type == "fixed_amount":
                trade_amount = min(config.position_size_value, cash)
            else:
                trade_amount = min(config.position_size_value * current_price, cash)

            if trade_amount > 0:
                shares_to_buy = int(trade_amount / current_price)
                if shares_to_buy > 0:
                    buy_amount = shares_to_buy * current_price
                    commission = buy_amount * config.commission_rate
                    stamp_duty = 0.0  # 买入时无印花税
                    total_cost = buy_amount + commission + stamp_duty

                    if total_cost <= cash:
                        cash -= total_cost
                        shares_held += shares_to_buy
                        trades.append(Trade(
                            date=row["date"],
                            type="buy",
                            price=current_price,
                            shares=shares_to_buy,
                            amount=buy_amount,
                            commission=commission,
                            stamp_duty=stamp_duty,
                            total_cost=total_cost
                        ))

        # 执行卖出
        elif sell_signal == 1 and shares_held > 0:
            sell_amount = shares_held * current_price
            commission = sell_amount * config.commission_rate
            stamp_duty = sell_amount * config.stamp_duty_rate
            proceeds = sell_amount - commission - stamp_duty

            cash += proceeds
            trades.append(Trade(
                date=row["date"],
                type="sell",
                price=current_price,
                shares=shares_held,
                amount=sell_amount,
                commission=commission,
                stamp_duty=stamp_duty,
                total_cost=commission + stamp_duty
            ))
            shares_held = 0

        # 计算当前净值
        current_value = cash + shares_held * current_price
        portfolio_values.append(current_value)

    # 数据结束时强制平仓
    if shares_held > 0:
        last_row = df.iloc[-1]
        current_price = last_row["close"]
        sell_amount = shares_held * current_price
        commission = sell_amount * config.commission_rate
        stamp_duty = sell_amount * config.stamp_duty_rate
        proceeds = sell_amount - commission - stamp_duty
        cash += proceeds
        trades.append(Trade(
            date=last_row["date"],
            type="sell",
            price=current_price,
            shares=shares_held,
            amount=sell_amount,
            commission=commission,
            stamp_duty=stamp_duty,
            total_cost=commission + stamp_duty
        ))
        shares_held = 0
        # 更新最后一天的净值
        portfolio_values[-1] = cash
        # 标记强制平仓为卖出信号，确保前端图表显示
        if "sell_signal" in df.columns:
            df.iloc[-1, df.columns.get_loc("sell_signal")] = 1

    df["portfolio_value"] = portfolio_values
    return _calculate_performance(df, trades, initial_capital)


def _calculate_performance(
    df: pd.DataFrame,
    trades: List[Trade],
    initial_capital: float
) -> BacktestResult:
    """计算绩效指标"""
    portfolio_values = pd.Series(df["portfolio_value"].values, index=df.index)
    final_value = portfolio_values.iloc[-1]

    # 总收益率
    total_return = (final_value - initial_capital) / initial_capital

    # 年化收益率 (假设一年252个交易日)
    days = len(df)
    cagr = (final_value / initial_capital) ** (252 / days) - 1 if days > 0 else 0.0

    # 最大回撤
    rolling_max = portfolio_values.cummax()
    drawdown = (portfolio_values - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    # 计算交易统计
    buy_trades = [t for t in trades if t.type == "buy"]
    sell_trades = [t for t in trades if t.type == "sell"]
    total_trades = len(sell_trades)  # 以完成的卖出次数计算完整交易

    winning_trades = 0
    losing_trades = 0
    profits = []
    holding_days_list = []

    # 配对买卖计算盈亏
    for buy, sell in zip(buy_trades[:len(sell_trades)], sell_trades):
        profit = (sell.price * sell.shares - sell.commission - sell.stamp_duty) - \
                 (buy.price * buy.shares + buy.commission)
        profits.append(profit)
        if profit > 0:
            winning_trades += 1
        elif profit < 0:
            losing_trades += 1
        try:
            buy_date = pd.to_datetime(buy.date)
            sell_date = pd.to_datetime(sell.date)
            holding_days_list.append((sell_date - buy_date).days)
        except Exception:
            pass

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    # 盈亏比
    avg_win = np.mean([p for p in profits if p > 0]) if winning_trades > 0 else 0.0
    avg_loss = abs(np.mean([p for p in profits if p < 0])) if losing_trades > 0 else 1.0
    reward_risk_ratio = avg_win / avg_loss if avg_loss != 0 else 0.0

    # 平均持仓天数
    avg_holding_days = float(np.mean(holding_days_list)) if holding_days_list else 0.0

    # 夏普比率（年化）
    daily_returns = portfolio_values.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe_ratio = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252))
    else:
        sharpe_ratio = 0.0

    return BacktestResult(
        df=df,
        trades=trades,
        portfolio_values=portfolio_values,
        initial_capital=initial_capital,
        final_capital=final_value,
        total_return=total_return,
        cagr=cagr,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        reward_risk_ratio=reward_risk_ratio,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_holding_days=avg_holding_days,
        sharpe_ratio=sharpe_ratio,
    )


def run_backtest_with_strategy(
    df,
    strategy,
    params: dict,
    initial_capital: Optional[float] = None,
    cost_override: Optional[dict] = None,
) -> BacktestResult:
    """
    用策略对象和参数运行回测（桥接策略系统与回测引擎）。

    Args:
        df: 含 OHLCV 的 DataFrame
        strategy: StrategyBase 实例
        params: 策略参数字典
        initial_capital: 初始资金
        cost_override: 可选费率覆盖，如 {"stamp_duty_rate": 0.0}（ETF 扩展点）

    Returns:
        BacktestResult
    """
    from .config import get_config

    config = get_config()
    saved = {}

    if cost_override:
        for key, val in cost_override.items():
            saved[key] = getattr(config, key, None)
            setattr(config, key, val)

    try:
        df_with_signals = strategy.generate_signals(df.copy(), params)
        result = run_backtest(df_with_signals, initial_capital)
    finally:
        for key, val in saved.items():
            setattr(config, key, val)

    return result


def trade_to_dict(trade: Trade) -> dict:
    """单条交易记录序列化"""
    return {
        "date": trade.date,
        "type": trade.type,
        "price": round(trade.price, 2),
        "shares": trade.shares,
        "amount": round(trade.amount, 2),
        "commission": round(trade.commission, 2),
        "stamp_duty": round(trade.stamp_duty, 2),
        "total_cost": round(trade.total_cost, 2),
    }


def backtest_result_to_dict(result: BacktestResult, include_trades: bool = True) -> dict:
    """回测结果序列化为 JSON 友好字典"""
    # 提取价格+信号数据用于前端绘制买卖标记图
    price_cols = ["date", "close", "buy_signal", "sell_signal"]
    band_cols = ["ma_mid", "boll_up", "boll_down"]
    available = [c for c in price_cols + band_cols if c in result.df.columns]
    price_data = {}
    for col in available:
        vals = result.df[col]
        if col == "date":
            price_data[col] = vals.astype(str).tolist()
        else:
            price_data[col] = [round(float(v), 2) if pd.notna(v) else None for v in vals]

    return {
        "initial_capital": result.initial_capital,
        "final_capital": round(result.final_capital, 2),
        "total_return": round(result.total_return, 4),
        "cagr": round(result.cagr, 4),
        "max_drawdown": round(result.max_drawdown, 4),
        "win_rate": round(result.win_rate, 4),
        "reward_risk_ratio": round(result.reward_risk_ratio, 2),
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "trades": [trade_to_dict(t) for t in result.trades] if include_trades else [],
        "portfolio_values": [round(v, 2) for v in result.portfolio_values.tolist()],
        "avg_holding_days": round(result.avg_holding_days, 1),
        "sharpe_ratio": round(result.sharpe_ratio, 4),
        "price_data": price_data,
    }


# === Phase 2: 多周期回测 ===
@dataclass
class MultiPeriodBacktestResult:
    """多周期回测结果（包含对比）"""
    # 多周期结果
    multi_result: BacktestResult
    # 单周期结果（用于对比）
    single_result: BacktestResult


def run_multi_period_backtest(
    symbol: str,
    initial_capital: Optional[float] = None
) -> MultiPeriodBacktestResult:
    """
    运行多周期回测，并与单周期进行对比

    Args:
        symbol: 股票代码
        initial_capital: 初始资金

    Returns:
        MultiPeriodBacktestResult，包含两种策略的回测结果
    """
    from src.config import get_config
    from src.data_fetcher import get_stock_data
    from src.bollinger import calculate_bollinger
    from src.signals import generate_signals

    config = get_config()
    initial_capital = initial_capital or config.initial_capital

    print("\n" + "=" * 60)
    print("PHASE 1: Single-Period Backtest (Benchmark)")
    print("=" * 60)

    # 1. 单周期回测（作为基准）
    df_single = get_stock_data(symbol, period="daily", use_cache=True)
    df_single = calculate_bollinger(df_single, config.bollinger_n, config.bollinger_m)
    df_single = generate_signals(df_single)
    single_result = run_backtest(df_single, initial_capital)

    print(f"\nBenchmark complete:")
    print(f"  Total return: {single_result.total_return:.2%}")
    print(f"  CAGR: {single_result.cagr:.2%}")
    print(f"  Max drawdown: {single_result.max_drawdown:.2%}")
    print(f"  Win rate: {single_result.win_rate:.2%}")
    print(f"  Trades: {single_result.total_trades}")

    print("\n" + "=" * 60)
    print("PHASE 2: Multi-Period Resonance Backtest")
    print("=" * 60)

    # 2. 多周期回测
    from src.multi_period import prepare_multi_period_backtest

    try:
        result_df, _ = prepare_multi_period_backtest(symbol, config)

        # 使用共振信号替换原始信号
        df_multi = result_df.copy()
        df_multi["buy_signal"] = df_multi.get("resonance_buy", 0)
        df_multi["sell_signal"] = df_multi.get("resonance_sell", 0)

        multi_result = run_backtest(df_multi, initial_capital)

        print(f"\nMulti-period strategy complete:")
        print(f"  Total return: {multi_result.total_return:.2%}")
        print(f"  CAGR: {multi_result.cagr:.2%}")
        print(f"  Max drawdown: {multi_result.max_drawdown:.2%}")
        print(f"  Win rate: {multi_result.win_rate:.2%}")
        print(f"  Trades: {multi_result.total_trades}")

        # 对比
        print("\n" + "-" * 60)
        print("COMPARISON:")
        print("-" * 60)
        outperf = (multi_result.total_return - single_result.total_return)
        print(f"  Outperformance: {outperf:.2%}")
        dd_improve = (single_result.max_drawdown - multi_result.max_drawdown)
        print(f"  Drawdown improvement: {dd_improve:.2%}")
        print("-" * 60)

    except Exception as e:
        print(f"Multi-period backtest failed: {e}")
        import traceback
        traceback.print_exc()
        # 失败时返回基准结果两次
        multi_result = single_result

    return MultiPeriodBacktestResult(
        multi_result=multi_result,
        single_result=single_result
    )
