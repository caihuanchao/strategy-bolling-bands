"""信号生成模块 - 基于布林带生成买卖信号 + 成交量验证"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Signal:
    """单只股票的信号结果"""
    symbol: str
    name: str
    date: str
    signal_type: str  # "BUY", "SELL", "NONE"
    price: float
    boll_up: float
    boll_mid: float
    boll_down: float
    volume_ratio: Optional[float] = None  # 成交量放大比例
    is_enhanced: bool = False  # 是否通过成交量验证（增强信号）


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    基于布林带生成买卖信号

    买入逻辑：收盘价跌破下轨 (close <= boll_down)
    卖出逻辑：收盘价突破上轨 (close >= boll_up)

    Args:
        df: 包含 close, boll_up, boll_down 列的 DataFrame

    Returns:
        添加了信号列的 DataFrame，包含：buy_signal, sell_signal (1/0)
    """
    df = df.copy()

    # 生成信号
    df["buy_signal"] = np.where(df["close"] <= df["boll_down"], 1, 0)
    df["sell_signal"] = np.where(df["close"] >= df["boll_up"], 1, 0)

    return df


def add_volume_analysis(
    df: pd.DataFrame,
    volume_window: int = 20
) -> pd.DataFrame:
    """
    添加成交量分析

    计算：
    - avg_volume: 前N日均量
    - volume_ratio: 今日成交量 / 均量

    Args:
        df: 包含 volume 列的 DataFrame
        volume_window: 均量窗口

    Returns:
        添加了成交量列的 DataFrame
    """
    df = df.copy()

    if "volume" in df.columns:
        df["avg_volume"] = df["volume"].rolling(window=volume_window).mean()
        df["volume_ratio"] = df["volume"] / df["avg_volume"]

    return df


def check_volume_enhanced(
    df: pd.DataFrame,
    volume_threshold: float = 1.5,  # 默认1.5倍均量
    volume_window: int = 20
) -> pd.DataFrame:
    """
    检查今日信号是否通过成交量验证

    Args:
        df: 包含 buy_signal, sell_signal, volume 的 DataFrame
        volume_threshold: 成交量放大阈值（相对于均量）
        volume_window: 均量窗口

    Returns:
        添加了增强信号标记的 DataFrame
    """
    df = df.copy()

    # 先加成交量分析
    if "volume_ratio" not in df.columns:
        df = add_volume_analysis(df, volume_window)

    # 标记：有信号且成交量放大 >= 阈值
    df["is_enhanced"] = np.where(
        ((df["buy_signal"] == 1) | (df["sell_signal"] == 1)) &
        (df["volume_ratio"] >= volume_threshold),
        True,
        False
    )

    return df


def scan_latest_signals(
    symbol: str,
    name: str,
    df: pd.DataFrame,
    volume_threshold: float = 1.5,
    volume_window: int = 20
) -> Optional[Signal]:
    """
    扫描一只股票的最新信号

    Args:
        symbol: 股票代码
        name: 股票名称
        df: 完整数据DataFrame（已算好布林带和信号）
        volume_threshold: 成交量放大阈值
        volume_window: 均量窗口

    Returns:
        有信号返回Signal对象，无信号返回None
    """
    if len(df) == 0:
        return None

    # 确保有信号列
    if "buy_signal" not in df.columns or "sell_signal" not in df.columns:
        df = generate_signals(df)

    # 确保有成交量分析
    df = check_volume_enhanced(df, volume_threshold, volume_window)

    # 取最新一行
    latest = df.iloc[-1]

    signal_type = "NONE"
    if latest["buy_signal"] == 1:
        signal_type = "BUY"
    elif latest["sell_signal"] == 1:
        signal_type = "SELL"

    if signal_type == "NONE":
        return None

    return Signal(
        symbol=symbol,
        name=name,
        date=latest["date"],
        signal_type=signal_type,
        price=float(latest["close"]),
        boll_up=float(latest.get("boll_up", 0)),
        boll_mid=float(latest.get("ma_mid", 0)),
        boll_down=float(latest.get("boll_down", 0)),
        volume_ratio=float(latest.get("volume_ratio", 1.0)) if pd.notna(latest.get("volume_ratio")) else None,
        is_enhanced=bool(latest.get("is_enhanced", False))
    )


def scan_all_signals(
    data_dict: dict,  # {symbol: (name, df)}
    volume_threshold: float = 1.5,
    volume_window: int = 20
) -> List[Signal]:
    """
    扫描所有股票的最新信号

    Args:
        data_dict: {symbol: (name, df)}
        volume_threshold: 成交量放大阈值
        volume_window: 均量窗口

    Returns:
        有信号的 Signal 对象列表
    """
    signals = []

    for symbol, (name, df) in data_dict.items():
        signal = scan_latest_signals(
            symbol=symbol,
            name=name,
            df=df,
            volume_threshold=volume_threshold,
            volume_window=volume_window
        )
        if signal:
            signals.append(signal)

    return signals
