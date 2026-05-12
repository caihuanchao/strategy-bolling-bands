"""自选股管理模块"""

import os
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StockInfo:
    """股票信息"""
    symbol: str
    name: str


def load_watchlist(filepath: str = "watchlist.csv") -> List[StockInfo]:
    """
    从 CSV 加载自选股

    CSV 格式要求：
    - 必须有列：symbol, name
    - 可选列：其他备注列

    Returns:
        StockInfo 列表
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"自选股文件不存在: {filepath}")

    # 自动检测分隔符（支持逗号或 Tab）
    with open(filepath, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
    sep = "\t" if "\t" in first_line else ","

    df = pd.read_csv(filepath, sep=sep, dtype=str)

    # 支持中文列名
    df = df.rename(columns={"代码": "symbol", "名称": "name"})

    # 检查必须的列
    required_cols = ["symbol", "name"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"CSV 缺少必须的列: {col}")

    # 转换为 StockInfo 列表
    stocks = []
    for _, row in df.iterrows():
        # 确保 symbol 是字符串，补零（只对短于5位的代码补零，保留港股5位代码）
        symbol = str(row["symbol"]).strip()
        if len(symbol) < 5:
            symbol = symbol.zfill(6)
        name = str(row["name"]).strip()
        stocks.append(StockInfo(symbol=symbol, name=name))

    return stocks


def create_sample_watchlist(filepath: str = "watchlist.csv"):
    """创建示例自选股文件"""
    sample_data = [
        {"symbol": "000333", "name": "美的集团"},
        {"symbol": "000001", "name": "平安银行"},
        {"symbol": "600519", "name": "贵州茅台"},
        {"symbol": "000858", "name": "五粮液"},
        {"symbol": "002594", "name": "比亚迪"},
    ]
    df = pd.DataFrame(sample_data)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"示例自选股文件已创建: {filepath}")
