"""交易单位（手）模块 — 获取和缓存股票每手股数"""

import os
import json

from .config import ensure_dirs


_CACHE_DIR = "data/cache"
_CACHE_FILE = os.path.join(_CACHE_DIR, "hk_lot_sizes.json")


def _is_hk(symbol: str) -> bool:
    """判断是否为港股（5 位数字代码）"""
    return len(symbol) == 5 and symbol.isdigit()


def load_lot_size_cache() -> dict:
    """从本地 JSON 加载港股每手股数缓存"""
    if not os.path.exists(_CACHE_FILE):
        return {}
    with open(_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_lot_size_cache(data: dict):
    """保存港股每手股数缓存到本地 JSON"""
    ensure_dirs()
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_hk_lot_sizes(symbols: list) -> dict:
    """通过 akshare 逐只获取港股每手股数"""
    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        # akshare 未安装时，港股默认 100 股/手
        return {s: 100 for s in symbols if _is_hk(s)}

    result = {}
    for sym in symbols:
        if not _is_hk(sym):
            continue
        try:
            df = ak.stock_hk_security_profile_em(symbol=sym)
            lot = int(df["每手股数"].iloc[0])
            result[sym] = lot
        except Exception:
            result[sym] = 100  # fallback: 默认 100 股/手
    return result


def get_lot_size_map(stocks: list) -> dict:
    """
    获取所有股票的每手股数映射。

    A 股/ETF 固定 100 股/手（默认）。
    港股从本地缓存读取，缓存未命中时通过 akshare 获取并写入缓存。

    Args:
        stocks: StockInfo 列表

    Returns:
        {symbol: lot_size} 字典
    """
    cache = load_lot_size_cache()
    hk_symbols = [s.symbol for s in stocks if _is_hk(s.symbol)]
    missing = [s for s in hk_symbols if s not in cache]

    if missing:
        fetched = fetch_hk_lot_sizes(missing)
        cache.update(fetched)
        save_lot_size_cache(cache)

    lot_map = {}
    for s in stocks:
        if _is_hk(s.symbol):
            lot_map[s.symbol] = cache.get(s.symbol, 100)
        else:
            lot_map[s.symbol] = 100

    return lot_map
