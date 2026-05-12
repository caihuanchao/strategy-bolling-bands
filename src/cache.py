"""缓存管理模块 - 保存和加载策略计算结果"""

import os
import re
import json
import pandas as pd
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from dataclasses import asdict

from .config import get_config, ensure_dirs
from .signals import Signal


def clean_filename_name(name: str) -> str:
    """
    清理股票名称用于文件名，替换特殊字符为下划线

    Args:
        name: 原始股票名称，如"*ST平安"、"美的集团"

    Returns:
        清理后的名称，如"_ST平安"、"美的集团"
    """
    # 替换特殊字符为下划线：空格、*、(、)、[、]、-、.、/、\
    return re.sub(r'[^\w一-鿿]', '_', name)


def get_bollinger_cache_path(symbol: str, name: Optional[str] = None) -> str:
    """
    获取布林带缓存文件路径

    Args:
        symbol: 股票代码
        name: 股票名称（可选），如果提供则使用新格式

    Returns:
        缓存文件路径
    """
    config = get_config()
    if name:
        clean_name = clean_filename_name(name)
        filename = f"{clean_name}_{symbol}.csv"
    else:
        filename = f"{symbol}.csv"
    return os.path.join(config.cache_bollinger_dir, filename)


def migrate_bollinger_cache():
    """迁移旧格式布林带缓存到新格式（包含名称）"""
    config = get_config()
    cache_dir = config.cache_bollinger_dir

    if not os.path.exists(cache_dir):
        return

    # 默认标的从配置获取名称进行迁移
    if config.symbol_name:
        old_path = os.path.join(cache_dir, f"{config.symbol}.csv")
        new_path = get_bollinger_cache_path(config.symbol, config.symbol_name)

        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                print(f"已迁移布林带缓存: {config.symbol}.csv -> {os.path.basename(new_path)}")
            except Exception as e:
                print(f"迁移布林带缓存失败: {e}")


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
    # 保存新格式
    filepath_new = get_bollinger_cache_path(symbol, name)
    filepath_old = get_bollinger_cache_path(symbol)

    # 确保有必要的列
    required_cols = ["date", "open", "high", "low", "close", "volume", "ma_mid", "boll_up", "boll_down"]
    available_cols = [c for c in required_cols if c in df.columns]
    save_df = df[available_cols].copy() if available_cols else df

    save_df.to_csv(filepath_new, index=False, encoding="utf-8-sig")

    # 删除旧文件（如果存在）
    if os.path.exists(filepath_old):
        try:
            os.remove(filepath_old)
            print(f"已删除旧布林带缓存: {os.path.basename(filepath_old)}")
        except Exception as e:
            print(f"删除旧布林带缓存失败: {e}")

    return filepath_new


def load_bollinger_history(symbol: str, name: Optional[str] = None) -> Optional[Tuple[str, pd.DataFrame]]:
    """
    加载单只股票的布林带历史

    Args:
        symbol: 股票代码
        name: 股票名称（可选），用于查找新格式文件

    Returns:
        (name, df) 元组，如果不存在返回 None
    """
    cfg = get_config()

    # 先尝试新格式
    if name:
        filepath_new = get_bollinger_cache_path(symbol, name)
        if os.path.exists(filepath_new):
            try:
                df = pd.read_csv(filepath_new)
                return (name, df)
            except Exception:
                pass

        # 尝试自动迁移旧文件
        filepath_old = get_bollinger_cache_path(symbol)
        if os.path.exists(filepath_old):
            try:
                os.rename(filepath_old, filepath_new)
                print(f"自动迁移布林带缓存: {os.path.basename(filepath_old)} -> {os.path.basename(filepath_new)}")
                df = pd.read_csv(filepath_new)
                return (name, df)
            except Exception as e:
                print(f"迁移失败，尝试加载旧格式: {e}")

    # 尝试旧格式
    filepath_old = get_bollinger_cache_path(symbol)
    if os.path.exists(filepath_old):
        try:
            df = pd.read_csv(filepath_old)
            # 旧格式返回 symbol 作为 name
            return (symbol, df)
        except Exception:
            pass

    return None
