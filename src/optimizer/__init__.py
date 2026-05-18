"""通用回测优化框架 — 策略无关的参数优化抽象"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class OptimizableParam:
    """策略可优化参数描述"""
    key: str            # "n"
    label: str          # "N (周期)"
    type: str           # "int" | "float"
    min: float
    max: float
    step: float         # 网格搜索步长
    default: float

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "type": self.type,
            "min": self.min, "max": self.max, "step": self.step, "default": self.default,
        }


@dataclass
class OptimizationResult:
    """参数优化结果"""
    strategy_id: str
    symbol: str
    symbol_name: str
    param_space: List[dict]           # OptimizableParam.to_dict() 列表
    best_params: dict                 # {"n": 15, "m": 1.75}
    best_metrics: dict                # 最优参数的绩效指标
    all_results: List[dict]           # [{"params": {...}, "metrics": {...}}, ...]
    total_combinations: int
    elapsed_seconds: float
    cached: bool = False
    optimize_metric: str = "total_return"

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "symbol_name": self.symbol_name,
            "param_space": self.param_space,
            "best_params": self.best_params,
            "best_metrics": self.best_metrics,
            "all_results": self.all_results,
            "total_combinations": self.total_combinations,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "cached": self.cached,
            "optimize_metric": self.optimize_metric,
        }


class BaseOptimizer(ABC):
    """优化器抽象基类"""

    @abstractmethod
    def optimize(
        self,
        strategy,
        df,
        param_space: List[OptimizableParam],
        initial_capital: float,
        cost_override: Optional[dict] = None,
        environment_filter: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        optimize_metric: str = "total_return",
        lot_size: int = 100,
    ) -> OptimizationResult:
        """
        执行参数优化。

        Args:
            strategy: StrategyBase 实例
            df: 含 OHLCV 的 DataFrame
            param_space: 可优化参数列表（含搜索范围）
            initial_capital: 初始资金
            cost_override: 可选费率覆盖，如 {"stamp_duty_rate": 0.0}（E 扩展点）
            environment_filter: 可选环境过滤，如 "trend"/"range"/"squeeze"（D 扩展点）
            progress_callback: 进度回调 (current, total)
            optimize_metric: 优化目标指标，默认 total_return
            lot_size: 每手股数，A 股固定 100，港股因股而异
        """
        ...
