"""多周期共振模块 - 数据对齐、共振逻辑"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass

from src.config import get_config, Config
from src.data_fetcher import get_stock_data
from src.bollinger import calculate_bollinger
from src.signals import generate_signals, add_volume_analysis
from src.indicators import calculate_all_indicators


@dataclass
class PeriodData:
    """单周期数据容器"""
    period: str
    df: pd.DataFrame
    has_bollinger: bool = False
    has_indicators: bool = False
    has_signals: bool = False


def normalize_date(date_val) -> str:
    """
    标准化日期格式，用于对齐

    将 "2025-01-01 09:30:00" 转换为 "2025-01-01"
    将 "2025-01-01" 保持原样
    将整数 20250102103000000 转换为 "2025-01-02"
    """
    date_str = str(date_val)

    # 处理长数字格式: 20250102103000000 -> "2025-01-02"
    if len(date_str) >= 8 and date_str.isdigit():
        return f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"

    # 处理空格分隔的格式
    if " " in date_str:
        return date_str.split(" ")[0]

    return date_str


def fetch_multi_period_data(
    symbol: str,
    periods: List[str],
    config: Optional[Config] = None,
    use_cache: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    获取多个周期的数据

    Args:
        symbol: 股票代码
        periods: 周期列表，如 ["daily", "4h", "1h"]
        config: 配置对象
        use_cache: 是否使用缓存

    Returns:
        {period: dataframe} 字典
    """
    if config is None:
        config = get_config()

    data_dict = {}
    for period in periods:
        print(f"\nFetching {period} data for {symbol}...")
        try:
            df = get_stock_data(
                symbol=symbol,
                period=period,
                start_date=config.start_date,
                use_cache=use_cache
            )
            data_dict[period] = df
            print(f"  ✓ {period}: {len(df)} rows")
        except Exception as e:
            print(f"  ✗ {period} failed: {e}")

    return data_dict


def align_multi_period_data(
    daily_df: pd.DataFrame,
    h4_df: Optional[pd.DataFrame] = None,
    h1_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    按日期对齐多周期数据（日线为主，小时线取最新）

    逻辑：
    - 以日线日期为基准
    - 对每个日线日期，找到小时线的最后一根K线
    - 将小时线指标合并到日线数据

    Args:
        daily_df: 日线数据
        h4_df: 4小时数据（可选）
        h1_df: 1小时数据（可选）

    Returns:
        对齐后的日线数据（包含其他周期的最新指标）
    """
    result_df = daily_df.copy()

    # 标准化日期列
    result_df["_date_key"] = result_df["date"].apply(normalize_date)

    if h4_df is not None and len(h4_df) > 0:
        h4_df = h4_df.copy()
        h4_df["_date_key"] = h4_df["date"].apply(normalize_date)
        # 取每天最后一根4小时K线
        h4_last = h4_df.groupby("_date_key").last().reset_index()
        # 重命名列避免冲突
        h4_last.columns = [
            f"h4_{c}" if c not in ["_date_key"] else c
            for c in h4_last.columns
        ]
        # 合并
        result_df = result_df.merge(
            h4_last,
            on="_date_key",
            how="left",
            suffixes=("", "_h4")
        )

    if h1_df is not None and len(h1_df) > 0:
        h1_df = h1_df.copy()
        h1_df["_date_key"] = h1_df["date"].apply(normalize_date)
        # 取每天最后一根1小时K线
        h1_last = h1_df.groupby("_date_key").last().reset_index()
        # 重命名列避免冲突
        h1_last.columns = [
            f"h1_{c}" if c not in ["_date_key"] else c
            for c in h1_last.columns
        ]
        # 合并
        result_df = result_df.merge(
            h1_last,
            on="_date_key",
            how="left",
            suffixes=("", "_h1")
        )

    # 清理临时列
    result_df = result_df.drop("_date_key", axis=1, errors="ignore")
    return result_df


def calculate_all_for_period(
    df: pd.DataFrame,
    config: Optional[Config] = None
) -> pd.DataFrame:
    """
    为单个周期计算所有指标（布林带 + MACD + RSI + 信号）

    Args:
        df: OHLCV 数据
        config: 配置对象

    Returns:
        计算了所有指标的 DataFrame
    """
    if config is None:
        config = get_config()

    df = df.copy()

    # 1. 布林带
    df = calculate_bollinger(df, config.bollinger_n, config.bollinger_m)

    # 2. 技术指标
    df = calculate_all_indicators(df, config)

    # 3. 基础信号
    df = generate_signals(df)

    # 4. 成交量分析
    df = add_volume_analysis(df, config.volume_window)

    return df


def check_resonance_signals(
    aligned_df: pd.DataFrame,
    config: Optional[Config] = None
) -> pd.DataFrame:
    """
    检查多周期共振信号

    买入共振：
    - 日线：收盘价跌破下轨
    - 4小时：收盘价 >= 中轨（趋势向上确认）或 RSI < 超卖
    - 1小时：RSI < 超卖（超卖确认）

    卖出共振：
    - 日线：收盘价突破上轨
    - 4小时：收盘价 <= 中轨（趋势向下确认）或 RSI > 超买
    - 1小时：RSI > 超买（超买确认）

    Args:
        aligned_df: 对齐后的多周期数据
        config: 配置对象

    Returns:
        添加了共振信号列的 DataFrame
    """
    if config is None:
        config = get_config()

    df = aligned_df.copy()

    # 默认无共振
    df["resonance_buy"] = 0
    df["resonance_sell"] = 0

    # 检查必要的列是否存在
    has_h4 = "h4_rsi" in df.columns or "h4_close" in df.columns
    has_h1 = "h1_rsi" in df.columns

    # === 买入共振逻辑 ===
    # 基础条件：日线有买入信号
    base_buy = df["buy_signal"] == 1

    # 4小时确认（如果有）
    h4_ok = True
    if has_h4:
        if "h4_ma_mid" in df.columns and "h4_close" in df.columns:
            # 4小时在中轨上方（趋势向上）或 RSI 超卖
            h4_trend_up = df["h4_close"] >= df["h4_ma_mid"]
            h4_oversold = df["h4_rsi"] <= config.rsi_oversold if "h4_rsi" in df.columns else False
            h4_ok = h4_trend_up | h4_oversold
        elif "h4_rsi" in df.columns:
            h4_ok = df["h4_rsi"] <= config.rsi_oversold

    # 1小时确认（如果有）
    h1_ok = True
    if has_h1 and "h1_rsi" in df.columns:
        h1_ok = df["h1_rsi"] <= config.rsi_oversold

    # 最终买入共振
    if config.resonance_require_all:
        # 严格模式：需要所有周期确认
        buy_condition = base_buy & h4_ok & h1_ok
    else:
        # 宽松模式：需要日线 + 至少1个小周期确认
        buy_condition = base_buy & (h4_ok | h1_ok)

    df.loc[buy_condition, "resonance_buy"] = 1

    # === 卖出共振逻辑 ===
    # 基础条件：日线有卖出信号
    base_sell = df["sell_signal"] == 1

    # 4小时确认（如果有）
    h4_sell_ok = True
    if has_h4:
        if "h4_ma_mid" in df.columns and "h4_close" in df.columns:
            # 4小时在中轨下方（趋势向下）或 RSI 超买
            h4_trend_down = df["h4_close"] <= df["h4_ma_mid"]
            h4_overbought = df["h4_rsi"] >= config.rsi_overbought if "h4_rsi" in df.columns else False
            h4_sell_ok = h4_trend_down | h4_overbought
        elif "h4_rsi" in df.columns:
            h4_sell_ok = df["h4_rsi"] >= config.rsi_overbought

    # 1小时确认（如果有）
    h1_sell_ok = True
    if has_h1 and "h1_rsi" in df.columns:
        h1_sell_ok = df["h1_rsi"] >= config.rsi_overbought

    # 最终卖出共振
    if config.resonance_require_all:
        sell_condition = base_sell & h4_sell_ok & h1_sell_ok
    else:
        sell_condition = base_sell & (h4_sell_ok | h1_sell_ok)

    df.loc[sell_condition, "resonance_sell"] = 1

    # 统计有多少周期确认（用于分析）
    df["confirm_count"] = 1  # 日线本身
    if has_h4:
        df["confirm_count"] += np.where((h4_ok & base_buy) | (h4_sell_ok & base_sell), 1, 0)
    if has_h1:
        df["confirm_count"] += np.where((h1_ok & base_buy) | (h1_sell_ok & base_sell), 1, 0)

    return df


def prepare_multi_period_backtest(
    symbol: str,
    config: Optional[Config] = None
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    准备多周期回测数据（一站式函数）

    Args:
        symbol: 股票代码
        config: 配置对象

    Returns:
        (对齐后的主数据, {period: 原始数据})
    """
    if config is None:
        config = get_config()

    # 1. 获取所有周期数据
    periods = list(config.periods)
    data_dict = fetch_multi_period_data(symbol, periods, config)

    if "daily" not in data_dict:
        raise ValueError("Daily data is required for multi-period strategy")

    # 2. 为每个周期计算指标
    enriched_dict = {}
    for period, df in data_dict.items():
        print(f"\nCalculating indicators for {period}...")
        enriched_dict[period] = calculate_all_for_period(df, config)
        print(f"  ✓ {period}: indicators calculated")

    # 3. 对齐数据
    print("\nAligning multi-period data...")
    daily_df = enriched_dict["daily"]
    h4_df = enriched_dict.get("4h") if "4h" in enriched_dict else enriched_dict.get("240")
    h1_df = enriched_dict.get("1h") if "1h" in enriched_dict else enriched_dict.get("60")

    aligned_df = align_multi_period_data(daily_df, h4_df, h1_df)
    print(f"  ✓ Aligned: {len(aligned_df)} rows")

    # 4. 检查共振信号
    print("\nChecking resonance signals...")
    result_df = check_resonance_signals(aligned_df, config)

    buy_count = (result_df["resonance_buy"] == 1).sum()
    sell_count = (result_df["resonance_sell"] == 1).sum()
    print(f"  ✓ Buy resonance: {buy_count}, Sell resonance: {sell_count}")

    return result_df, enriched_dict
