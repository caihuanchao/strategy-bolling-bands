"""缓存管理模块 - 保存和加载策略计算结果"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from dataclasses import asdict

from .config import get_config, ensure_dirs
from .signals import Signal


def save_metadata(
    config,
    scan_time: datetime,
    buy_count: int,
    sell_count: int,
    enhanced_count: int,
    total_stocks: int
) -> str:
    """
    保存元数据到 JSON

    Args:
        config: 配置对象
        scan_time: 扫描时间
        buy_count: 买入信号数量
        sell_count: 卖出信号数量
        enhanced_count: 增强信号数量
        total_stocks: 总股票数

    Returns:
        保存的文件路径
    """
    ensure_dirs()
    cfg = get_config()
    filepath = os.path.join(cfg.cache_base_dir, "metadata.json")

    metadata = {
        "scan_time": scan_time.isoformat(),
        "bollinger_n": config.bollinger_n,
        "bollinger_m": config.bollinger_m,
        "volume_threshold": 1.5,  # 可以从配置或参数传入
        "volume_window": 20,
        "total_stocks": total_stocks,
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "enhanced_signals": enhanced_count
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return filepath


def load_metadata() -> Optional[Dict]:
    """
    加载元数据

    Returns:
        元数据字典，如果不存在返回 None
    """
    cfg = get_config()
    filepath = os.path.join(cfg.cache_base_dir, "metadata.json")

    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_signals(signals: List[Signal]) -> str:
    """
    保存信号列表到 CSV

    Args:
        signals: Signal 对象列表

    Returns:
        保存的文件路径
    """
    ensure_dirs()
    cfg = get_config()
    filepath = os.path.join(cfg.cache_base_dir, "signals.csv")

    if not signals:
        # 即使没有信号也要创建空文件（包含表头）
        empty_df = pd.DataFrame(columns=[
            "symbol", "name", "date", "signal_type", "price",
            "boll_up", "boll_mid", "boll_down", "volume_ratio", "is_enhanced"
        ])
        empty_df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath

    # 转换 Signal 对象为字典列表
    data = []
    for s in signals:
        data.append({
            "symbol": s.symbol,
            "name": s.name,
            "date": s.date,
            "signal_type": s.signal_type,
            "price": s.price,
            "boll_up": s.boll_up,
            "boll_mid": s.boll_mid,
            "boll_down": s.boll_down,
            "volume_ratio": s.volume_ratio,
            "is_enhanced": s.is_enhanced
        })

    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    return filepath


def load_signals() -> Optional[pd.DataFrame]:
    """
    加载信号 CSV

    Returns:
        信号 DataFrame，如果不存在返回 None
    """
    cfg = get_config()
    filepath = os.path.join(cfg.cache_base_dir, "signals.csv")

    if not os.path.exists(filepath):
        return None

    try:
        df = pd.read_csv(filepath)
        return df
    except Exception:
        return None


def save_bollinger_history(symbol: str, name: str, df: pd.DataFrame) -> str:
    """
    保存单只股票的布林带历史到 CSV

    Args:
        symbol: 股票代码
        name: 股票名称
        df: 包含布林带数据的 DataFrame

    Returns:
        保存的文件路径
    """
    ensure_dirs()
    cfg = get_config()
    filepath = os.path.join(cfg.cache_bollinger_dir, f"{symbol}.csv")

    # 保存时包含股票名称元信息（可以放在文件开头注释或单独列）
    # 这里简单处理：直接保存 df，文件名包含 symbol

    # 确保有必要的列
    required_cols = ["date", "open", "high", "low", "close", "volume", "ma_mid", "boll_up", "boll_down"]
    available_cols = [c for c in required_cols if c in df.columns]
    save_df = df[available_cols].copy() if available_cols else df

    save_df.to_csv(filepath, index=False, encoding="utf-8-sig")

    return filepath


def load_bollinger_history(symbol: str) -> Optional[Tuple[str, pd.DataFrame]]:
    """
    加载单只股票的布林带历史

    Args:
        symbol: 股票代码

    Returns:
        (name, df) 元组，如果不存在返回 None
        (注意：name 暂时只能从文件名推断，后续可以优化存储方式)
    """
    cfg = get_config()
    filepath = os.path.join(cfg.cache_bollinger_dir, f"{symbol}.csv")

    if not os.path.exists(filepath):
        return None

    try:
        df = pd.read_csv(filepath)
        # 暂时 name 设为 symbol，后续可以优化存储方式
        name = symbol
        return (name, df)
    except Exception:
        return None
