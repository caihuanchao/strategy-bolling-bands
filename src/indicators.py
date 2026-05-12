"""技术指标模块 - MACD、RSI 等计算"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    计算指数移动平均线 (EMA)

    Args:
        series: 价格序列
        period: EMA 周期

    Returns:
        EMA 序列
    """
    return series.ewm(span=period, adjust=False).mean()


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    price_col: str = "close"
) -> pd.DataFrame:
    """
    计算 MACD 指标

    Args:
        df: 包含价格的 DataFrame
        fast: 快速 EMA 周期
        slow: 慢速 EMA 周期
        signal: 信号线周期
        price_col: 价格列名

    Returns:
        添加了 macd, signal, histogram 列的 DataFrame
    """
    df = df.copy()

    # 计算 EMA
    ema_fast = calculate_ema(df[price_col], fast)
    ema_slow = calculate_ema(df[price_col], slow)

    # MACD 线 = 快 EMA - 慢 EMA
    df["macd"] = ema_fast - ema_slow

    # 信号线 = MACD 的 EMA
    df["macd_signal"] = calculate_ema(df["macd"], signal)

    # MACD 柱 = MACD - 信号线
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    return df


def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
    price_col: str = "close"
) -> pd.DataFrame:
    """
    计算 RSI (相对强弱指标)

    Args:
        df: 包含价格的 DataFrame
        period: RSI 周期
        price_col: 价格列名

    Returns:
        添加了 rsi 列的 DataFrame
    """
    df = df.copy()

    # 计算价格变化
    delta = df[price_col].diff()

    # 分离上涨和下跌
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    # 计算相对强弱 (RS)
    rs = gain / loss

    # 计算 RSI
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


def check_rsi_signal(
    df: pd.DataFrame,
    overbought: float = 70.0,
    oversold: float = 30.0
) -> pd.DataFrame:
    """
    检查 RSI 超买超卖信号

    Args:
        df: 包含 rsi 列的 DataFrame
        overbought: 超买阈值
        oversold: 超卖阈值

    Returns:
        添加了 rsi_overbought, rsi_oversold 列的 DataFrame
    """
    df = df.copy()

    if "rsi" not in df.columns:
        df = calculate_rsi(df)

    df["rsi_overbought"] = np.where(df["rsi"] >= overbought, 1, 0)
    df["rsi_oversold"] = np.where(df["rsi"] <= oversold, 1, 0)

    return df


def check_macd_signal(df: pd.DataFrame) -> pd.DataFrame:
    """
    检查 MACD 交叉信号

    Args:
        df: 包含 macd, macd_signal 列的 DataFrame

    Returns:
        添加了 macd_bullish_cross, macd_bearish_cross 列的 DataFrame
    """
    df = df.copy()

    if "macd" not in df.columns or "macd_signal" not in df.columns:
        df = calculate_macd(df)

    # MACD 上穿信号线（金叉）
    df["macd_bullish_cross"] = np.where(
        (df["macd"] > df["macd_signal"]) &
        (df["macd"].shift(1) <= df["macd_signal"].shift(1)),
        1, 0
    )

    # MACD 下穿信号线（死叉）
    df["macd_bearish_cross"] = np.where(
        (df["macd"] < df["macd_signal"]) &
        (df["macd"].shift(1) >= df["macd_signal"].shift(1)),
        1, 0
    )

    return df


def calculate_all_indicators(
    df: pd.DataFrame,
    config: Optional[object] = None
) -> pd.DataFrame:
    """
    一次性计算所有技术指标（MACD + RSI）

    Args:
        df: OHLCV 数据
        config: 配置对象，包含 macd_fast, macd_slow, macd_signal, rsi_period 等

    Returns:
        添加了所有指标列的 DataFrame
    """
    df = df.copy()

    # 从配置读取参数，或使用默认值
    macd_fast = getattr(config, "macd_fast", 12)
    macd_slow = getattr(config, "macd_slow", 26)
    macd_signal = getattr(config, "macd_signal", 9)
    rsi_period = getattr(config, "rsi_period", 14)

    # 计算 MACD
    df = calculate_macd(df, macd_fast, macd_slow, macd_signal)

    # 计算 RSI
    df = calculate_rsi(df, rsi_period)

    # 计算信号标记
    df = check_macd_signal(df)
    df = check_rsi_signal(
        df,
        overbought=getattr(config, "rsi_overbought", 70.0),
        oversold=getattr(config, "rsi_oversold", 30.0)
    )

    return df
