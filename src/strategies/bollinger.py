"""布林带触碰策略 — 价格触及上下轨产生买卖信号"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal


class BollingerStrategy(StrategyBase):
    """布林带触碰策略：收盘价跌破下轨→买入，突破上轨→卖出"""

    strategy_id = "bollinger"
    strategy_name = "布林带触碰"

    def get_default_params(self) -> dict:
        return {"n": 20, "m": 2.0}

    def get_params_schema(self) -> list:
        return [
            {"key": "n", "label": "N (周期)", "min": 5, "max": 50, "step": 1, "default": 20},
            {"key": "m", "label": "M (倍数)", "min": 1.0, "max": 3.0, "step": 0.1, "default": 2.0},
        ]

    def get_presets(self) -> list:
        return [
            {"id": "trend", "label": "趋势跟踪", "params": {"n": 20, "m": 2.0}, "desc": "标准参数，适合趋势行情"},
            {"id": "oscillating", "label": "震荡市", "params": {"n": 10, "m": 1.5}, "desc": "短周期窄带，适合震荡行情"},
            {"id": "high_vol", "label": "高波动", "params": {"n": 30, "m": 2.5}, "desc": "长周期宽带，适合高波动行情"},
            {"id": "tight", "label": "收紧", "params": {"n": 15, "m": 1.8}, "desc": "中短周期，提前捕捉变盘"},
        ]

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        n = int(params.get("n", 20))
        m = float(params.get("m", 2.0))

        # 布林带计算（如果尚未计算或需要重算）
        df["ma_mid"] = df["close"].rolling(window=n).mean()
        df["std"] = df["close"].rolling(window=n).std()
        df["boll_up"] = df["ma_mid"] + m * df["std"]
        df["boll_down"] = df["ma_mid"] - m * df["std"]

        # 买卖信号
        df["buy_signal"] = np.where(df["close"] <= df["boll_down"], 1, 0)
        df["sell_signal"] = np.where(df["close"] >= df["boll_up"], 1, 0)

        # 成交量分析
        if "volume" in df.columns:
            df["avg_volume"] = df["volume"].rolling(window=20).mean()
            df["volume_ratio"] = df["volume"] / df["avg_volume"]
            df["is_enhanced"] = np.where(
                ((df["buy_signal"] == 1) | (df["sell_signal"] == 1)) &
                (df["volume_ratio"] >= 1.5),
                True, False
            )
        else:
            df["volume_ratio"] = np.nan
            df["is_enhanced"] = False

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
            boll_up=float(row.get("boll_up", 0)),
            boll_mid=float(row.get("ma_mid", 0)),
            boll_down=float(row.get("boll_down", 0)),
            volume_ratio=vol_ratio,
            is_enhanced=bool(row.get("is_enhanced", False)),
            metadata={
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                ],
            },
        )
