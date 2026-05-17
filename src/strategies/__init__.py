"""策略注册中心 - 多策略架构基础"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import pandas as pd


class StrategyBase(ABC):
    """策略抽象基类，所有策略必须实现此接口"""

    strategy_id: str = ""       # 唯一标识，如 "bollinger", "dual_ma"
    strategy_name: str = ""     # 显示名称，如 "布林带触碰", "双均线交叉"

    @abstractmethod
    def get_default_params(self) -> dict:
        """返回策略默认参数，如 {"n": 20, "m": 2.0}"""
        ...

    @abstractmethod
    def get_params_schema(self) -> list:
        """
        返回参数面板 schema，用于前端动态渲染滑块。
        格式: [{"key": "n", "label": "周期 N", "min": 5, "max": 50, "step": 1, "default": 20}, ...]
        """
        ...

    @abstractmethod
    def get_presets(self) -> list:
        """
        返回策略预设模板。
        格式: [{"id": "trend", "label": "趋势跟踪", "params": {"n": 20, "m": 2.0}, "desc": "适合趋势行情"}, ...]
        """
        ...

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        基于当前参数生成买卖信号列。
        必须添加列: buy_signal (0/1), sell_signal (0/1)
        可选添加策略专属列。

        Args:
            df: OHLCV DataFrame（需含 close, volume 等列）
            params: 策略参数字典

        Returns:
            添加了 buy_signal, sell_signal 列的 DataFrame
        """
        ...

    @abstractmethod
    def create_signal(self, symbol: str, name: str, df: pd.DataFrame,
                      idx: int, params: dict) -> Optional["Signal"]:
        """
        从 DataFrame 的指定行创建 Signal 对象。
        返回 None 表示该行无有效信号。

        Args:
            symbol: 股票代码
            name: 股票名称
            df: 含信号列的 DataFrame
            idx: 行索引
            params: 策略参数
        """
        ...


    def get_optimizable_params(self) -> list:
        """
        返回可优化参数列表。默认返回空列表（策略不可优化）。
        子类可覆盖此方法声明可优化参数。
        """
        return []


class StrategyRegistry:
    """策略注册中心（单例模式）"""

    def __init__(self):
        self._strategies: Dict[str, StrategyBase] = {}

    def register(self, strategy: StrategyBase):
        """注册一个策略"""
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> StrategyBase:
        """获取指定策略，不存在则 fallback 到布林带"""
        if strategy_id in self._strategies:
            return self._strategies[strategy_id]
        return self._strategies.get("bollinger")

    def list_all(self) -> List[dict]:
        """列出所有已注册策略的摘要信息"""
        return [
            {
                "id": s.strategy_id,
                "name": s.strategy_name,
                "params_schema": s.get_params_schema(),
                "default_params": s.get_default_params(),
            }
            for s in self._strategies.values()
        ]
