"""信号生成模块 - 基于布林带生成买卖信号"""

import pandas as pd
import numpy as np


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
