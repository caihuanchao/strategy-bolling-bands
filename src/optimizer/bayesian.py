"""贝叶斯优化器 — Optuna TPE + 粗网格初始化"""

import math
import time
from typing import Optional, Callable, List

import optuna

from src.optimizer import BaseOptimizer, OptimizableParam, OptimizationResult
from src.backtest import run_backtest_with_strategy, backtest_result_to_dict


class BayesianOptimizer(BaseOptimizer):
    """基于 Optuna TPE 的贝叶斯优化器：粗网格初始覆盖 + 智能采样"""

    def _generate_coarse_grid(self, param_space: List[OptimizableParam], n_points: int) -> list:
        """生成均匀覆盖参数空间的初始点列表"""
        n_params = len(param_space)
        if n_params == 0:
            return []

        # 每维度取 ceil(n_points^(1/n_params)) 个点
        per_dim = max(2, math.ceil(n_points ** (1.0 / n_params)))
        dim_values = []
        for p in param_space:
            if p.type == "int":
                step = max(p.step, 1)
                vals = []
                v = p.min
                while v <= p.max + 1e-9:
                    vals.append(int(v))
                    v += step
                # 降采样到 per_dim 个
                if len(vals) > per_dim:
                    indices = [int(i * (len(vals) - 1) / (per_dim - 1)) for i in range(per_dim)]
                    vals = [vals[i] for i in indices]
            else:
                vals = []
                for i in range(per_dim):
                    t = i / (per_dim - 1) if per_dim > 1 else 0.5
                    v = p.min + t * (p.max - p.min)
                    # 对齐到 step 的倍数
                    v = round(v / p.step) * p.step if p.step > 0 else v
                    v = round(v, 6)
                    v = max(p.min, min(p.max, v))
                    vals.append(v)
            dim_values.append(vals)

        # 生成全组合，截断到 n_points
        import itertools
        grid = list(itertools.product(*dim_values))
        if len(grid) > n_points:
            step = len(grid) / n_points
            grid = [grid[int(i * step)] for i in range(n_points)]
        return [dict(zip([p.key for p in param_space], combo)) for combo in grid]

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
        n_initial: int = 15,
        n_trials: int = 45,
        n_no_improve: int = 10,
    ) -> OptimizationResult:
        start_time = time.time()
        all_results = []

        # 生成粗网格初始点
        initial_points = self._generate_coarse_grid(param_space, n_initial)

        # 构建 study
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        # enqueue 粗网格点
        for pt in initial_points:
            study.enqueue_trial(pt)

        # 记录早停状态
        best_so_far = float("-inf")
        no_improve_count = 0

        def _objective(trial):
            nonlocal best_so_far, no_improve_count

            params = {}
            for p in param_space:
                if p.type == "int":
                    params[p.key] = trial.suggest_int(p.key, int(p.min), int(p.max), step=max(int(p.step), 1))
                else:
                    params[p.key] = trial.suggest_float(p.key, p.min, p.max, step=p.step)

            result = run_backtest_with_strategy(
                df, strategy, params, initial_capital, cost_override
            )
            metrics = backtest_result_to_dict(result, include_trades=True)

            # 派生指标
            holding = max(metrics.get("avg_holding_days", 0), 1)
            if metrics.get("total_trades", 0) == 0:
                metrics["efficiency_ratio"] = 0.0
            else:
                metrics["efficiency_ratio"] = round(metrics["total_return"] / holding, 6)

            trial.set_user_attr("params", params)
            trial.set_user_attr("metrics", metrics)

            value = metrics.get(optimize_metric, metrics["total_return"])
            if value > best_so_far:
                best_so_far = value
                no_improve_count = 0
            else:
                no_improve_count += 1

            # 提前终止（仅对 TPE 阶段生效，粗网格阶段不中止）
            if trial.number >= n_initial and no_improve_count >= n_no_improve:
                raise optuna.TrialPruned()

            return value

        def _progress_wrapper(study, trial):
            if progress_callback:
                progress_callback(trial.number + 1, n_trials)

        try:
            study.optimize(
                _objective,
                n_trials=n_trials,
                callbacks=[_progress_wrapper],
                n_jobs=1,
            )
        except Exception:
            pass  # 早停或其他中断

        # 收集所有完成的 trial 结果
        completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        for t in completed:
            all_results.append({
                "params": t.user_attrs.get("params", t.params),
                "metrics": t.user_attrs.get("metrics", {}),
            })

        if not all_results:
            # fallback：所有 trial 都被 prune 或其他异常
            return OptimizationResult(
                strategy_id=strategy.strategy_id,
                symbol="", symbol_name="",
                param_space=[p.to_dict() for p in param_space],
                best_params={}, best_metrics={},
                all_results=[], total_combinations=0,
                elapsed_seconds=time.time() - start_time,
                cached=False, optimize_metric=optimize_metric,
            )

        # 按 optimize_metric 排序
        all_results.sort(key=lambda x: x["metrics"].get(optimize_metric, 0), reverse=True)
        best = all_results[0]

        return OptimizationResult(
            strategy_id=strategy.strategy_id,
            symbol="", symbol_name="",
            param_space=[p.to_dict() for p in param_space],
            best_params=best["params"],
            best_metrics=best["metrics"],
            all_results=all_results,
            total_combinations=len(all_results),
            elapsed_seconds=time.time() - start_time,
            cached=False,
            optimize_metric=optimize_metric,
        )
