"""成交量分析策略 — 量价背离、放量突破、缩量回调、OBV、形态识别"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal


class VolumeAnalysisStrategy(StrategyBase):
    """成交量分析策略：量价综合 + OBV + 形态识别 + 轻量共振"""

    strategy_id = "volume_analysis"
    strategy_name = "成交量分析"

    def get_default_params(self) -> dict:
        return {
            "divergence_lookback": 20,
            "volume_ratio_threshold": 1.5,
            "contraction_threshold": 0.5,
            "obv_divergence_window": 20,
        }

    def get_params_schema(self) -> list:
        return [
            {"key": "divergence_lookback", "label": "背离检测回望周期", "min": 10, "max": 40, "step": 5, "default": 20},
            {"key": "volume_ratio_threshold", "label": "放量阈值", "min": 1.2, "max": 3.0, "step": 0.1, "default": 1.5},
            {"key": "contraction_threshold", "label": "缩量阈值", "min": 0.3, "max": 0.8, "step": 0.1, "default": 0.5},
            {"key": "obv_divergence_window", "label": "OBV背离窗口", "min": 10, "max": 40, "step": 5, "default": 20},
        ]

    def get_presets(self) -> list:
        return [
            {"id": "standard", "label": "标准", "params": {"divergence_lookback": 20, "volume_ratio_threshold": 1.5, "contraction_threshold": 0.5, "obv_divergence_window": 20}, "desc": "标准参数，适合中短线"},
            {"id": "sensitive", "label": "敏感", "params": {"divergence_lookback": 10, "volume_ratio_threshold": 1.3, "contraction_threshold": 0.6, "obv_divergence_window": 10}, "desc": "更快响应，适合短线"},
            {"id": "lagged", "label": "滞后", "params": {"divergence_lookback": 30, "volume_ratio_threshold": 2.0, "contraction_threshold": 0.4, "obv_divergence_window": 30}, "desc": "减少假信号，适合中长线"},
        ]

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        n = len(df)
        lookback = int(params.get("divergence_lookback", 20))
        vol_threshold = float(params.get("volume_ratio_threshold", 1.5))
        contraction_th = float(params.get("contraction_threshold", 0.5))
        obv_window = int(params.get("obv_divergence_window", 20))

        # ── 成交量和量比 ──
        if "volume" not in df.columns:
            df["volume"] = 0
        df["avg_volume"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = np.where(
            df["avg_volume"] > 0,
            df["volume"] / df["avg_volume"],
            1.0
        )

        # ── 价格变化 ──
        df["price_change"] = df["close"].diff()

        # ── OBV 计算 ──
        df["obv"] = 0.0
        if n > 0:
            df.loc[df.index[0], "obv"] = float(df.loc[df.index[0], "volume"])
        for i in range(1, n):
            prev_close = df["close"].iloc[i - 1]
            cur_close = df["close"].iloc[i]
            prev_obv = df["obv"].iloc[i - 1]
            cur_vol = df["volume"].iloc[i]
            if pd.isna(prev_close) or pd.isna(cur_close) or pd.isna(prev_obv) or pd.isna(cur_vol):
                df.loc[df.index[i], "obv"] = prev_obv if not pd.isna(prev_obv) else 0
            elif cur_close > prev_close:
                df.loc[df.index[i], "obv"] = prev_obv + cur_vol
            elif cur_close < prev_close:
                df.loc[df.index[i], "obv"] = prev_obv - cur_vol
            else:
                df.loc[df.index[i], "obv"] = prev_obv

        # ── 价格极值和量比（滚动窗口） ──
        df["close_rolling_max"] = df["close"].rolling(window=lookback).max()
        df["close_rolling_min"] = df["close"].rolling(window=lookback).min()

        # 记录价格创新高/新低时的量比
        df["is_price_high"] = (df["close"] >= df["close_rolling_max"].shift(1)) & (df.index >= lookback)
        df["is_price_low"] = (df["close"] <= df["close_rolling_min"].shift(1)) & (df.index >= lookback)

        # ── 量价背离检测 ──
        df["divergence_top"] = 0
        df["divergence_bottom"] = 0

        for i in range(lookback * 2, n):
            if df["is_price_high"].iloc[i]:
                # 找到上一次价格高点区间 [i-2*lookback, i-lookback] 的峰值量比
                prev_start = max(0, i - 2 * lookback)
                prev_end = i - lookback
                prev_slice = df.iloc[prev_start:prev_end + 1]
                prev_highs = prev_slice[prev_slice["is_price_high"]]
                if len(prev_highs) > 0:
                    prev_peak_vr = prev_highs["volume_ratio"].max()
                    cur_vr = df["volume_ratio"].iloc[i]
                    if cur_vr < prev_peak_vr * 0.8:  # 量比明显低于前高
                        df.loc[df.index[i], "divergence_top"] = 1

            if df["is_price_low"].iloc[i]:
                prev_start = max(0, i - 2 * lookback)
                prev_end = i - lookback
                prev_slice = df.iloc[prev_start:prev_end + 1]
                prev_lows = prev_slice[prev_slice["is_price_low"]]
                if len(prev_lows) > 0:
                    prev_low_vr = prev_lows["volume_ratio"].min()
                    cur_vr = df["volume_ratio"].iloc[i]
                    if cur_vr < prev_low_vr * 0.7:  # 量比明显萎缩
                        df.loc[df.index[i], "divergence_bottom"] = 1

        # ── 放量突破 ──
        df["breakout_buy"] = np.where(
            (df["volume_ratio"] >= vol_threshold) &
            (df["price_change"] > 0) &
            (df.index >= 20),
            1, 0
        )

        # ── 缩量回调（上升趋势中） ──
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["price_high_5"] = df["close"].rolling(window=5).max()
        df["is_uptrend"] = df["close"] > df["ma20"]
        df["is_pullback"] = df["close"] < df["price_high_5"].shift(1) * 0.97
        df["is_volume_contracted"] = df["volume_ratio"] < contraction_th
        df["stopped_falling"] = df["price_change"] >= 0  # 当日止跌

        df["contraction_buy"] = np.where(
            df["is_uptrend"] &
            df["is_pullback"] &
            df["is_volume_contracted"] &
            df["stopped_falling"] &
            (df.index >= 20),
            1, 0
        )

        # ── 形态评分（量价关系：涨放量+1, 涨缩量-1, 跌放量-1, 跌缩量+1） ──
        df["pattern_score"] = 0.0
        for i in range(1, n):
            pc = df["price_change"].iloc[i]
            vr = df["volume_ratio"].iloc[i]
            if pd.isna(pc) or pd.isna(vr):
                continue
            if pc > 0 and vr >= 1.0:
                df.loc[df.index[i], "pattern_score"] = 1.0    # 涨放量 → 健康
            elif pc > 0 and vr < 1.0:
                df.loc[df.index[i], "pattern_score"] = -1.0   # 涨缩量 → 动力衰竭
            elif pc < 0 and vr >= 1.0:
                df.loc[df.index[i], "pattern_score"] = -1.0   # 跌放量 → 抛压重
            elif pc < 0 and vr < 1.0:
                df.loc[df.index[i], "pattern_score"] = 1.0    # 跌缩量 → 卖盘枯竭

        # 平滑形态评分（10日累加）
        df["pattern_score_sum"] = df["pattern_score"].rolling(window=10).sum()

        # ── 成交量高潮 ──
        df["pattern_climax_buy"] = 0   # 卖出高潮（底部）
        df["pattern_climax_sell"] = 0  # 买入高潮（顶部）

        for i in range(20, n):
            vr = df["volume_ratio"].iloc[i]
            close_i = df["close"].iloc[i]
            if pd.isna(vr) or pd.isna(close_i):
                continue
            if vr >= 3.0:
                # 判断位置：在近20日高点附近 → 买入高潮（顶部），近20日低点附近 → 卖出高潮（底部）
                high_20 = df["close"].iloc[max(0, i - 20):i].max()
                low_20 = df["close"].iloc[max(0, i - 20):i].min()
                if close_i >= high_20 * 0.95:
                    df.loc[df.index[i], "pattern_climax_sell"] = 1
                elif close_i <= low_20 * 1.05:
                    df.loc[df.index[i], "pattern_climax_buy"] = 1

        # ── 轻量共振：条件计数 ──
        df["cond_divergence"] = df["divergence_bottom"]  # 底背离条件
        df["cond_breakout"] = df["breakout_buy"]          # 放量突破条件
        df["cond_contraction"] = df["contraction_buy"]    # 缩量回调条件
        df["cond_obv_bullish"] = 0
        df["cond_pattern_bullish"] = (df["pattern_score_sum"] >= 2.0).astype(int)
        df["cond_pattern_bearish"] = (df["pattern_score_sum"] <= -2.0).astype(int)
        df["cond_climax_sell"] = df["pattern_climax_sell"]  # 买入高潮→卖出信号

        # OBV 趋势：近5日 OBV 上升
        obv_arr = df["obv"].values
        for i in range(5, n):
            if obv_arr[i] > obv_arr[i - 5] * 1.01:
                df.loc[df.index[i], "cond_obv_bullish"] = 1

        # 买入条件计数
        df["conditions_met"] = (
            df["cond_divergence"] +
            df["cond_breakout"] +
            df["cond_contraction"] +
            df["cond_obv_bullish"] +
            df["cond_pattern_bullish"]
        )

        # 卖出条件计数
        df["sell_conditions_met"] = (
            df["divergence_top"].astype(int) +
            df["cond_pattern_bearish"].astype(int) +
            df["cond_climax_sell"].astype(int)
        )

        # ── 买卖信号 ──
        df["buy_signal"] = np.where(
            (df["divergence_bottom"] == 1) |
            (df["breakout_buy"] == 1) |
            (df["contraction_buy"] == 1) |
            ((df["cond_obv_bullish"] == 1) & (df["cond_pattern_bullish"] == 1)),
            1, 0
        )

        df["sell_signal"] = np.where(
            (df["divergence_top"] == 1) |
            (df["pattern_climax_sell"] == 1) |
            ((df["cond_pattern_bearish"] == 1) & (df["volume_ratio"] >= 1.0)),
            1, 0
        )

        # ── 增强信号 ──
        df["is_enhanced"] = np.where(
            ((df["buy_signal"] == 1) | (df["sell_signal"] == 1)) &
            (df["conditions_met"] >= 2),
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

        conditions = int(row.get("conditions_met", 0))
        obv_val = float(row.get("obv", 0)) if pd.notna(row.get("obv")) else None
        pattern_sum = float(row.get("pattern_score_sum", 0)) if pd.notna(row.get("pattern_score_sum")) else 0

        # 形态标签
        if pattern_sum >= 3.0:
            pattern_label = "吸筹建仓"
        elif pattern_sum <= -3.0:
            pattern_label = "派发出货"
        elif int(row.get("pattern_climax_buy", 0)) == 1:
            pattern_label = "卖出高潮（潜在底部）"
        elif int(row.get("pattern_climax_sell", 0)) == 1:
            pattern_label = "买入高潮（潜在顶部）"
        elif abs(pattern_sum) < 1.0:
            pattern_label = "缩量整理"
        else:
            pattern_label = "无明显形态"

        # 成交量等级
        if vol_ratio is not None:
            if vol_ratio >= 3.0:
                vol_level = "天量"
            elif vol_ratio >= 2.0:
                vol_level = "显著放量"
            elif vol_ratio >= params.get("volume_ratio_threshold", 1.5):
                vol_level = "温和放量"
            elif vol_ratio >= 1.0:
                vol_level = "正常"
            else:
                vol_level = "缩量"
        else:
            vol_level = "N/A"

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
                "obv": obv_val,
                "volume_ratio": vol_ratio,
                "volume_level": vol_level,
                "conditions_met": conditions,
                "pattern_score": round(pattern_sum, 1),
                "pattern_label": pattern_label,
                "has_divergence": bool(row.get("divergence_top") or row.get("divergence_bottom")),
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                    {"key": "volume_level", "label": "成交量等级", "format": "text"},
                    {"key": "conditions_met", "label": "共振条件数", "format": "text"},
                    {"key": "pattern_label", "label": "形态", "format": "text"},
                ],
            },
        )
