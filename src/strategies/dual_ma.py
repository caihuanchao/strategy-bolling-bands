"""双均线交叉策略 — EMA 金叉死叉 + 成交量确认"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal


class DualMAStrategy(StrategyBase):
    """双均线交叉策略：EMA 快线上穿慢线→金叉买入，下穿→死叉卖出"""

    strategy_id = "dual_ma"
    strategy_name = "双均线交叉"

    def get_default_params(self) -> dict:
        return {"fast_period": 5, "slow_period": 20, "volume_threshold": 1.2}

    def get_params_schema(self) -> list:
        return [
            {"key": "fast_period", "label": "快线周期 (EMA)", "min": 2, "max": 20, "step": 1, "default": 5},
            {"key": "slow_period", "label": "慢线周期 (EMA)", "min": 5, "max": 60, "step": 1, "default": 20},
            {"key": "volume_threshold", "label": "量比阈值", "min": 1.0, "max": 3.0, "step": 0.1, "default": 1.2},
        ]

    def get_presets(self) -> list:
        return [
            {"id": "standard", "label": "标准", "params": {"fast_period": 5, "slow_period": 20, "volume_threshold": 1.2}, "desc": "经典5/20组合"},
            {"id": "sensitive", "label": "敏感", "params": {"fast_period": 3, "slow_period": 15, "volume_threshold": 1.0}, "desc": "更快响应，适合短线"},
            {"id": "lagged", "label": "滞后", "params": {"fast_period": 10, "slow_period": 30, "volume_threshold": 1.5}, "desc": "减少假信号，适合中长线"},
        ]

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        fast = int(params.get("fast_period", 5))
        slow = int(params.get("slow_period", 20))
        vol_threshold = float(params.get("volume_threshold", 1.2))

        # 计算 EMA
        df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()

        # 成交量均线
        if "volume" in df.columns:
            df["avg_volume"] = df["volume"].rolling(window=20).mean()
            df["volume_ratio"] = df["volume"] / df["avg_volume"]
        else:
            df["volume_ratio"] = 1.0

        # 金叉：快线上穿慢线 + 放量确认
        df["buy_signal"] = np.where(
            (df["ema_fast"] > df["ema_slow"]) &
            (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1)) &
            (df["volume_ratio"] >= vol_threshold),
            1, 0
        )

        # 死叉：快线下穿慢线 + 放量确认
        df["sell_signal"] = np.where(
            (df["ema_fast"] < df["ema_slow"]) &
            (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1)) &
            (df["volume_ratio"] >= vol_threshold),
            1, 0
        )

        # 增强标记
        df["is_enhanced"] = np.where(
            ((df["buy_signal"] == 1) | (df["sell_signal"] == 1)) &
            (df["volume_ratio"] >= vol_threshold),
            True, False
        )

        return df

    def create_signal(self, symbol: str, name: str, df: pd.DataFrame,
                      idx: int, params: dict) -> Optional[Signal]:
        if idx < 0 or idx >= len(df):
            return None

        row = df.iloc[idx]

        signal_type = "NONE"
        if row.get("buy_signal") == 1:
            signal_type = "BUY"
        elif row.get("sell_signal") == 1:
            signal_type = "SELL"

        if signal_type == "NONE":
            return None

        vol_ratio = float(row.get("volume_ratio", 1.0)) if pd.notna(row.get("volume_ratio")) else None

        return Signal(
            symbol=symbol,
            name=name,
            date=str(row.get("date", "")),
            signal_type=signal_type,
            price=float(row["close"]),
            strategy_id=self.strategy_id,
            volume_ratio=vol_ratio,
            is_enhanced=bool(row.get("is_enhanced", False)),
            metadata={
                "ema_fast": float(row.get("ema_fast", 0)) if pd.notna(row.get("ema_fast")) else None,
                "ema_slow": float(row.get("ema_slow", 0)) if pd.notna(row.get("ema_slow")) else None,
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "ema_fast", "label": "快线 EMA", "format": "price"},
                    {"key": "ema_slow", "label": "慢线 EMA", "format": "price"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                ],
            },
        )
