"""自选股管理模块"""

import os
import csv
import glob
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_GROUPS = ["A股", "港股", "ETF", "可转债", "其他"]


@dataclass
class StockInfo:
    """股票信息"""
    symbol: str
    name: str
    lot_size: int = 100
    group: str = "未分组"


def _detect_sep(filepath: str) -> str:
    """自动检测 CSV 分隔符"""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
    return "\t" if "\t" in first_line else ","


def load_watchlist(filepath: str = "watchlist.csv") -> List[StockInfo]:
    """
    从 CSV 加载自选股

    CSV 格式要求：
    - 必须有列：代码/symbol, 名称/name
    - 可选列：分组/group

    Returns:
        StockInfo 列表
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"自选股文件不存在: {filepath}")

    sep = _detect_sep(filepath)
    df = pd.read_csv(filepath, sep=sep, dtype=str)

    # 支持中文列名
    df = df.rename(columns={"代码": "symbol", "名称": "name", "分组": "group"})

    # 检查必须的列
    required_cols = ["symbol", "name"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"CSV 缺少必须的列: {col}")

    # 转换为 StockInfo 列表
    stocks = []
    for _, row in df.iterrows():
        symbol = str(row["symbol"]).strip()
        if len(symbol) < 5:
            symbol = symbol.zfill(6)
        name = str(row["name"]).strip()
        group = str(row.get("group", "")).strip() if "group" in df.columns and pd.notna(row.get("group")) else "未分组"
        if not group:
            group = "未分组"
        stocks.append(StockInfo(symbol=symbol, name=name, group=group))

    return stocks


def save_watchlist(stocks: List[StockInfo], filepath: str = "watchlist.csv"):
    """将自选股列表写入 CSV 文件（TAB 分隔，中文表头）"""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["代码", "名称", "分组"])
        for s in stocks:
            writer.writerow([s.symbol, s.name, s.group])
    print(f"自选股已保存: {filepath} ({len(stocks)} 只)")


def add_stock(symbol: str, name: str = "", group: str = "未分组",
              filepath: str = "watchlist.csv") -> bool:
    """
    添加个股到自选股列表

    Args:
        symbol: 股票代码
        name: 股票名称（为空时使用 symbol）
        group: 分组
        filepath: CSV 文件路径

    Returns:
        True 如果添加成功，False 如果已存在
    """
    stocks = load_watchlist(filepath)
    symbol = symbol.strip()
    # 补齐 A 股代码
    if len(symbol) < 5:
        symbol = symbol.zfill(6)

    # 去重
    for s in stocks:
        if s.symbol == symbol:
            print(f"股票 {symbol} 已存在，跳过添加")
            return False

    name = name.strip() if name.strip() else symbol
    group = group.strip() if group.strip() else "未分组"
    stocks.append(StockInfo(symbol=symbol, name=name, group=group))
    save_watchlist(stocks, filepath)
    return True


def remove_stock(symbol: str, filepath: str = "watchlist.csv") -> bool:
    """
    从自选股列表中删除个股，并清理关联缓存文件

    Args:
        symbol: 股票代码
        filepath: CSV 文件路径

    Returns:
        True 如果删除成功，False 如果未找到
    """
    stocks = load_watchlist(filepath)
    symbol = symbol.strip()
    if len(symbol) < 5:
        symbol = symbol.zfill(6)

    # 找到被删除股票的 name（用于清理缓存）
    removed_name = None
    for s in stocks:
        if s.symbol == symbol:
            removed_name = s.name
            break

    new_stocks = [s for s in stocks if s.symbol != symbol]
    if len(new_stocks) == len(stocks):
        print(f"股票 {symbol} 未找到")
        return False

    save_watchlist(new_stocks, filepath)

    # 清理关联缓存文件
    if removed_name:
        _cleanup_cache(symbol, removed_name)

    return True


def _cleanup_cache(symbol: str, name: str):
    """清理个股相关的缓存文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "..", "data")
    bollinger_dir = os.path.join(data_dir, "cache", "bollinger")

    cleaned = 0

    # 1. data/{name}_{symbol}_daily_*.csv 和 .meta.json
    safe_name = name.replace("/", "_").replace("\\", "_")
    patterns = [
        os.path.join(data_dir, f"{safe_name}_{symbol}_daily_*.csv"),
        os.path.join(data_dir, f"{safe_name}_{symbol}_daily_*.meta.json"),
    ]
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                os.remove(f)
                cleaned += 1
                print(f"  已删除: {os.path.basename(f)}")
            except OSError as e:
                print(f"  删除失败: {os.path.basename(f)} ({e})")

    # 2. data/cache/bollinger/{name}_{symbol}.csv
    bollinger_file = os.path.join(bollinger_dir, f"{safe_name}_{symbol}.csv")
    if os.path.exists(bollinger_file):
        try:
            os.remove(bollinger_file)
            cleaned += 1
            print(f"  已删除: bollinger/{os.path.basename(bollinger_file)}")
        except OSError as e:
            print(f"  删除失败: bollinger/{os.path.basename(bollinger_file)} ({e})")

    if cleaned > 0:
        print(f"缓存清理完成: {cleaned} 个文件")
    else:
        print("无关联缓存文件需要清理")


def create_sample_watchlist(filepath: str = "watchlist.csv"):
    """创建示例自选股文件"""
    sample_data = [
        {"symbol": "000333", "name": "美的集团", "group": "A股"},
        {"symbol": "000001", "name": "平安银行", "group": "A股"},
        {"symbol": "600519", "name": "贵州茅台", "group": "A股"},
        {"symbol": "000858", "name": "五粮液", "group": "A股"},
        {"symbol": "002594", "name": "比亚迪", "group": "A股"},
    ]
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["代码", "名称", "分组"])
        for s in sample_data:
            writer.writerow([s["symbol"], s["name"], s["group"]])
    print(f"示例自选股文件已创建: {filepath}")
