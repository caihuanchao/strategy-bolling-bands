"""优化结果磁盘缓存 — 避免重复计算"""

import hashlib
import json
import os
from typing import Optional

from src.optimizer import OptimizationResult

_cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", "optimizer")


def _ensure_cache_dir():
    os.makedirs(_cache_dir, exist_ok=True)


def _make_cache_key(
    strategy_id: str,
    symbol: str,
    params_json: str,
    data_first_date: str,
    data_last_date: str,
    optimize_metric: str = "total_return",
    optimizer_type: str = "grid",
) -> str:
    """生成缓存 key（SHA256 前 16 位）"""
    raw = f"{strategy_id}|{symbol}|{params_json}|{data_first_date}|{data_last_date}|{optimize_metric}|{optimizer_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_cached_result(cache_key: str) -> Optional[OptimizationResult]:
    """读取缓存结果"""
    _ensure_cache_dir()
    path = os.path.join(_cache_dir, f"{cache_key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        data["cached"] = True
        return OptimizationResult(
            strategy_id=data["strategy_id"],
            symbol=data["symbol"],
            symbol_name=data.get("symbol_name", ""),
            param_space=data.get("param_space", []),
            best_params=data.get("best_params", {}),
            best_metrics=data.get("best_metrics", {}),
            all_results=data.get("all_results", []),
            total_combinations=data.get("total_combinations", 0),
            elapsed_seconds=data.get("elapsed_seconds", 0),
            cached=True,
            optimize_metric=data.get("optimize_metric", "total_return"),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_cached_result(cache_key: str, result: OptimizationResult):
    """保存结果到缓存"""
    _ensure_cache_dir()
    path = os.path.join(_cache_dir, f"{cache_key}.json")
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
