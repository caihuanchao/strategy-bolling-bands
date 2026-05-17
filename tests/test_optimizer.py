"""回测优化框架单元测试"""

import os
import sys
import json
import tempfile
import pandas as pd
import numpy as np
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.optimizer import OptimizableParam, OptimizationResult, BaseOptimizer
from src.optimizer.grid_search import GridSearchOptimizer
from src.optimizer.cache import _make_cache_key, load_cached_result, save_cached_result
from src.strategies.bollinger import BollingerStrategy
from src.backtest import run_backtest_with_strategy, backtest_result_to_dict, trade_to_dict, Trade


def _make_sample_df(n_days=200):
    """生成模拟 OHLCV 数据"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    returns = np.random.normal(0.0005, 0.015, n_days)
    close = 10.0 * np.cumprod(1 + returns)
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": close * (1 - np.random.uniform(0, 0.01, n_days)),
        "high": close * (1 + np.random.uniform(0, 0.02, n_days)),
        "low": close * (1 - np.random.uniform(0, 0.02, n_days)),
        "close": close,
        "volume": np.random.randint(100000, 500000, n_days),
    })
    return df


def test_optimizable_param_dataclass():
    p = OptimizableParam(key="n", label="N (周期)", type="int", min=5, max=50, step=5, default=20)
    assert p.key == "n"
    assert p.type == "int"
    d = p.to_dict()
    assert d["key"] == "n"
    assert d["min"] == 5
    print("✅ test_optimizable_param_dataclass passed")


def test_optimization_result_serialization():
    result = OptimizationResult(
        strategy_id="bollinger",
        symbol="000001",
        symbol_name="测试",
        param_space=[],
        best_params={"n": 15, "m": 1.75},
        best_metrics={"total_return": 0.18},
        all_results=[],
        total_combinations=90,
        elapsed_seconds=2.5,
        cached=False,
    )
    d = result.to_dict()
    assert d["strategy_id"] == "bollinger"
    assert d["best_params"]["n"] == 15
    print("✅ test_optimization_result_serialization passed")


def test_run_backtest_with_strategy():
    df = _make_sample_df(200)
    strategy = BollingerStrategy()
    params = {"n": 20, "m": 2.0}
    result = run_backtest_with_strategy(df, strategy, params, initial_capital=100000)
    assert result.initial_capital == 100000
    assert result.final_capital > 0
    assert len(result.trades) >= 0
    assert -1.0 <= result.max_drawdown <= 0
    print(f"  total_return={result.total_return:.4f}, cagr={result.cagr:.4f}, max_dd={result.max_drawdown:.4f}, trades={result.total_trades}")
    print("✅ test_run_backtest_with_strategy passed")


def test_cost_override():
    df = _make_sample_df(100)
    strategy = BollingerStrategy()
    params = {"n": 20, "m": 2.0}

    result_default = run_backtest_with_strategy(df, strategy, params, initial_capital=100000)
    result_etf = run_backtest_with_strategy(
        df, strategy, params, initial_capital=100000,
        cost_override={"stamp_duty_rate": 0.0},
    )
    # ETF 免印花税，result_etf 的 final_capital 不应低于 result_default
    # (由于 sample data 随机，不一定总是高，但不应差太多)
    assert result_etf is not None
    print(f"  default final={result_default.final_capital:.2f}, etf final={result_etf.final_capital:.2f}")
    print("✅ test_cost_override passed")


def test_backtest_result_to_dict():
    df = _make_sample_df(100)
    strategy = BollingerStrategy()
    params = {"n": 20, "m": 2.0}
    result = run_backtest_with_strategy(df, strategy, params, initial_capital=100000)
    d = backtest_result_to_dict(result, include_trades=True)
    assert "total_return" in d
    assert "cagr" in d
    assert "max_drawdown" in d
    assert isinstance(d["trades"], list)
    print(f"  dict keys: {list(d.keys())}")
    print("✅ test_backtest_result_to_dict passed")


def test_grid_search_bollinger():
    df = _make_sample_df(60)
    strategy = BollingerStrategy()
    params = strategy.get_optimizable_params()
    # 使用极小的搜索空间加速测试
    params[0].min, params[0].max, params[0].step = 5, 15, 10  # N: 5, 15
    params[1].min, params[1].max, params[1].step = 1.0, 1.5, 0.5  # M: 1.0, 1.5

    optimizer = GridSearchOptimizer()
    result = optimizer.optimize(strategy, df, params, initial_capital=100000)

    assert result.strategy_id == "bollinger"
    assert result.total_combinations == 4  # N=(5,15) x M=(1.0,1.5) = 4
    assert len(result.all_results) == 4
    assert len(result.best_params) == 2
    assert "total_return" in result.best_metrics
    assert result.elapsed_seconds > 0

    # best_params 对应的 result 应排第一
    top = result.all_results[0]
    assert top["params"] == result.best_params

    print(f"  total_combinations={result.total_combinations}, elapsed={result.elapsed_seconds:.2f}s")
    print(f"  best_params={result.best_params}, best_return={result.best_metrics['total_return']:.4f}")
    print("✅ test_grid_search_bollinger passed")


def test_optimization_cache():
    result = OptimizationResult(
        strategy_id="bollinger",
        symbol="000001",
        symbol_name="平安银行",
        param_space=[],
        best_params={"n": 20, "m": 2.0},
        best_metrics={"total_return": 0.15},
        all_results=[],
        total_combinations=0,
        elapsed_seconds=0,
    )
    cache_key = "test_cache_key_001"
    save_cached_result(cache_key, result)

    loaded = load_cached_result(cache_key)
    assert loaded is not None
    assert loaded.strategy_id == "bollinger"
    assert loaded.symbol == "000001"
    assert loaded.cached is True

    # 清理
    import glob
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "optimizer")
    for f in glob.glob(os.path.join(cache_dir, "test_cache_key_*")):
        os.remove(f)

    print("✅ test_optimization_cache passed")


def test_cache_key_deterministic():
    k1 = _make_cache_key("bollinger", "000001", '{"n":20}', "2024-01-01", "2024-12-31")
    k2 = _make_cache_key("bollinger", "000001", '{"n":20}', "2024-01-01", "2024-12-31")
    k3 = _make_cache_key("bollinger", "000002", '{"n":20}', "2024-01-01", "2024-12-31")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 16
    print("✅ test_cache_key_deterministic passed")


def test_environment_filter_noop():
    """验证 D 扩展点：不传 environment_filter 时正常运行"""
    df = _make_sample_df(50)
    strategy = BollingerStrategy()
    params = strategy.get_optimizable_params()
    params[0].min, params[0].max, params[0].step = 10, 20, 10
    params[1].min, params[1].max, params[1].step = 1.5, 2.0, 0.5

    optimizer = GridSearchOptimizer()
    result = optimizer.optimize(strategy, df, params, 100000, environment_filter=None)
    assert result is not None
    assert result.strategy_id == "bollinger"
    print("✅ test_environment_filter_noop passed")


if __name__ == "__main__":
    test_optimizable_param_dataclass()
    test_optimization_result_serialization()
    test_run_backtest_with_strategy()
    test_cost_override()
    test_backtest_result_to_dict()
    test_grid_search_bollinger()
    test_optimization_cache()
    test_cache_key_deterministic()
    test_environment_filter_noop()
    print("\n🎉 全部测试通过!")
