"""网格搜索优化器 — 遍历参数空间找到最优组合"""

import itertools
import time
from typing import Optional, Callable, List

from src.optimizer import BaseOptimizer, OptimizableParam, OptimizationResult
from src.backtest import run_backtest_with_strategy, backtest_result_to_dict


class GridSearchOptimizer(BaseOptimizer):
    """网格搜索优化器：暴力遍历所有参数组合"""

    def _generate_combinations(self, param_space: List[OptimizableParam]) -> list:
        """生成所有参数组合"""
        values_list = []
        for p in param_space:
            if p.type == "int":
                values = []
                v = p.min
                while v <= p.max + 1e-9:
                    values.append(int(v))
                    v += p.step
            else:
                values = []
                v = p.min
                while v <= p.max + 1e-9:
                    values.append(round(v, 6))
                    v += p.step
            values_list.append(values)
        return list(itertools.product(*values_list))

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
        start_time = time.time()

        combinations = self._generate_combinations(param_space)
        total = len(combinations)
        all_results = []

        param_keys = [p.key for p in param_space]

        for idx, combo in enumerate(combinations):
            params = dict(zip(param_keys, combo))

            result = run_backtest_with_strategy(
                df, strategy, params, initial_capital, cost_override, lot_size=lot_size
            )
            metrics = backtest_result_to_dict(result, include_trades=True)

            all_results.append({
                "params": params,
                "metrics": metrics,
            })

            if progress_callback:
                progress_callback(idx + 1, total)

        # 为每条结果补充派生指标
        for r in all_results:
            m = r["metrics"]
            holding = max(m.get("avg_holding_days", 0), 1)
            if m.get("total_trades", 0) == 0:
                m["efficiency_ratio"] = 0.0
            else:
                m["efficiency_ratio"] = round(m["total_return"] / holding, 6)

        # 按选定的指标降序排列
        def _sort_key(x):
            return x["metrics"].get(optimize_metric, x["metrics"]["total_return"])
        all_results.sort(key=_sort_key, reverse=True)

        best = all_results[0]
        elapsed = time.time() - start_time

        return OptimizationResult(
            strategy_id=strategy.strategy_id,
            symbol="",  # 由调用方填充
            symbol_name="",
            param_space=[p.to_dict() for p in param_space],
            best_params=best["params"],
            best_metrics=best["metrics"],
            all_results=all_results,
            total_combinations=total,
            elapsed_seconds=elapsed,
            cached=False,
            optimize_metric=optimize_metric,
        )
