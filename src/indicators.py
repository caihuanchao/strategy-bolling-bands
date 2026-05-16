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


def calculate_kdj(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    """
    计算 KDJ 指标 (随机指标改良版)

    Args:
        df: 包含 high, low, close 列的 DataFrame
        n: RSV 周期 (默认 9)

    Returns:
        添加了 kdj_k, kdj_d, kdj_j 列的 DataFrame
    """
    df = df.copy()
    length = len(df)

    k = np.full(length, np.nan)
    d = np.full(length, np.nan)
    j = np.full(length, np.nan)

    if length < n:
        df["kdj_k"] = k
        df["kdj_d"] = d
        df["kdj_j"] = j
        return df

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    # 初始 K/D 值 = 50
    k_val = 50.0
    d_val = 50.0

    for i in range(length):
        if i < n - 1:
            k[i] = np.nan
            d[i] = np.nan
            j[i] = np.nan
            continue

        n_high = np.max(high[i - n + 1:i + 1])
        n_low = np.min(low[i - n + 1:i + 1])

        if n_high == n_low:
            rsv = 50.0  # 避免除零，返回中性值
        else:
            rsv = (close[i] - n_low) / (n_high - n_low) * 100.0

        k_val = 2.0 / 3.0 * k_val + 1.0 / 3.0 * rsv
        d_val = 2.0 / 3.0 * d_val + 1.0 / 3.0 * k_val
        j_val = 3.0 * k_val - 2.0 * d_val

        k[i] = k_val
        d[i] = d_val
        j[i] = j_val

    df["kdj_k"] = k
    df["kdj_d"] = d
    df["kdj_j"] = j

    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算 ATR (平均真实波幅) — Wilder 平滑法

    Args:
        df: 包含 high, low, close 列的 DataFrame
        period: ATR 周期 (默认 14)

    Returns:
        添加了 atr 列的 DataFrame
    """
    df = df.copy()
    n = len(df)

    if n < period + 1:
        df["atr"] = np.nan
        return df

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    tr = np.zeros(n)
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    # Wilder RMA 平滑
    atr = np.zeros(n)
    atr[period] = np.mean(tr[1:period + 1])
    for i in range(period + 1, n):
        atr[i] = atr[i - 1] + (tr[i] - atr[i - 1]) / period

    df["atr"] = atr

    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算 ADX (平均趋向指数) — Wilder 平滑法
    """
    df = df.copy()
    n = len(df)

    if n < period + 1:
        df["adx"] = np.nan
        df["plus_di"] = np.nan
        df["minus_di"] = np.nan
        return df

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        else:
            plus_dm[i] = 0

        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
        else:
            minus_dm[i] = 0

    # Wilder 平滑 (RMA): 首值为 SMA，后续 prev + (val - prev) / period
    tr_smooth = np.zeros(n)
    plus_dm_smooth = np.zeros(n)
    minus_dm_smooth = np.zeros(n)

    tr_smooth[period] = np.mean(tr[1:period + 1])
    plus_dm_smooth[period] = np.mean(plus_dm[1:period + 1])
    minus_dm_smooth[period] = np.mean(minus_dm[1:period + 1])

    for i in range(period + 1, n):
        tr_smooth[i] = tr_smooth[i - 1] + (tr[i] - tr_smooth[i - 1]) / period
        plus_dm_smooth[i] = plus_dm_smooth[i - 1] + (plus_dm[i] - plus_dm_smooth[i - 1]) / period
        minus_dm_smooth[i] = minus_dm_smooth[i - 1] + (minus_dm[i] - minus_dm_smooth[i - 1]) / period

    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    dx = np.zeros(n)

    for i in range(period, n):
        if tr_smooth[i] > 0:
            plus_di[i] = 100.0 * plus_dm_smooth[i] / tr_smooth[i]
            minus_di[i] = 100.0 * minus_dm_smooth[i] / tr_smooth[i]
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

    adx = np.zeros(n)
    adx[2 * period - 1] = np.mean(dx[period:2 * period])
    for i in range(2 * period, n):
        adx[i] = adx[i - 1] + (dx[i] - adx[i - 1]) / period

    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    return df
