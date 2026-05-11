"""布林带计算模块"""

import pandas as pd
from typing import Optional

from .config import get_config


def calculate_bollinger(
    df: pd.DataFrame,
    n: Optional[int] = None,
    m: Optional[float] = None
) -> pd.DataFrame:
    """
    计算布林带指标

    Args:
        df: 包含 close 列的 DataFrame
        n: 周期数，默认使用配置
        m: 标准差倍数，默认使用配置

    Returns:
        添加了布林带指标的 DataFrame，包含列：ma_mid, std, boll_up, boll_down
    """
    config = get_config()
    n = n or config.bollinger_n
    m = m or config.bollinger_m

    df = df.copy()
    df["ma_mid"] = df["close"].rolling(window=n).mean()
    df["std"] = df["close"].rolling(window=n).std()
    df["boll_up"] = df["ma_mid"] + m * df["std"]
    df["boll_down"] = df["ma_mid"] - m * df["std"]

    return df
