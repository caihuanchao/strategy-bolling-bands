"""周线 RSI 策略 — 基于周线 RSI 背离和超买超卖的中长线策略"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal
from src.indicators import calculate_rsi


class WeeklyRsiStrategy(StrategyBase):
    """周线 RSI 策略：日线 resample 周线 → RSI 背离 + 超买超卖信号"""

    strategy_id = "weekly_rsi"
    strategy_name = "周线RSI"

    # ── 参数常量 ──
    RSI_MIDLINE = 50

    def get_default_params(self) -> dict:
        return {
            "rsi_period": 14,
            "rsi_oversold": 35,
            "rsi_overbought": 65,
            "divergence_lookback": 20,
        }

    def get_params_schema(self) -> list:
        return [
            {"key": "rsi_period", "label": "RSI 周期", "min": 9, "max": 21, "step": 2, "default": 14},
            {"key": "rsi_oversold", "label": "超卖阈值", "min": 30, "max": 40, "step": 5, "default": 35},
            {"key": "rsi_overbought", "label": "超买阈值", "min": 60, "max": 70, "step": 5, "default": 65},
            {"key": "divergence_lookback", "label": "背离检测窗口", "min": 10, "max": 30, "step": 5, "default": 20},
        ]

    def get_presets(self) -> list:
        return [
            {
                "id": "standard",
                "label": "标准参数",
                "params": {"rsi_period": 14, "rsi_oversold": 35, "rsi_overbought": 65, "divergence_lookback": 20},
                "desc": "周线 RSI(14) + 35/65 分界，经典中长线参数",
            },
            {
                "id": "sensitive",
                "label": "敏感",
                "params": {"rsi_period": 9, "rsi_oversold": 40, "rsi_overbought": 60, "divergence_lookback": 15},
                "desc": "更短周期 + 更窄阈值，更快捕捉信号，适合高波动品种",
            },
            {
                "id": "conservative",
                "label": "保守",
                "params": {"rsi_period": 21, "rsi_oversold": 30, "rsi_overbought": 70, "divergence_lookback": 30},
                "desc": "长周期 + 宽阈值，减少假信号，适合低波动蓝筹",
            },
        ]

    def get_optimizable_params(self) -> list:
        from src.optimizer import OptimizableParam
        return [
            OptimizableParam(key="rsi_period", label="RSI 周期", type="int",
                             min=9, max=21, step=2, default=14),
            OptimizableParam(key="rsi_oversold", label="超卖阈值", type="int",
                             min=30, max=40, step=5, default=35),
            OptimizableParam(key="rsi_overbought", label="超买阈值", type="int",
                             min=60, max=70, step=5, default=65),
            OptimizableParam(key="divergence_lookback", label="背离检测窗口", type="int",
                             min=10, max=30, step=5, default=20),
        ]

    # ═══════════════════════════════════════════════════════════════
    # 日线 → 周线 resample
    # ═══════════════════════════════════════════════════════════════

    def _resample_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """将日线 DataFrame resample 为周线 (W-FRI)"""
        df_idx = df.copy()
        if "_date" not in df_idx.columns:
            df_idx["_date"] = pd.to_datetime(df_idx["date"], errors="coerce")
        df_idx = df_idx.dropna(subset=["_date"])
        df_idx = df_idx.set_index("_date")
        df_idx = df_idx.sort_index()

        weekly = pd.DataFrame({
            "close": df_idx["close"].resample("W-FRI").last(),
            "volume": df_idx.get("volume", pd.Series(0, index=df_idx.index)).resample("W-FRI").sum(),
        }).dropna(subset=["close"])

        return weekly

    # ═══════════════════════════════════════════════════════════════
    # 背离检测（在周线数据上）
    # ═══════════════════════════════════════════════════════════════

    def _detect_divergence(self, weekly: pd.DataFrame, lookback: int) -> pd.DataFrame:
        """检测周线 RSI 底背离和顶背离"""
        n = len(weekly)
        weekly["rsi_bottom_divergence"] = 0
        weekly["rsi_top_divergence"] = 0

        if n < lookback:
            return weekly

        close = weekly["close"].values
        rsi = weekly["rsi"].values

        for i in range(lookback, n):
            if pd.isna(close[i]) or pd.isna(rsi[i]):
                continue

            prev_close = close[i - lookback:i]
            prev_rsi = rsi[i - lookback:i]
            valid = ~np.isnan(prev_close) & ~np.isnan(prev_rsi)
            if valid.sum() < max(lookback // 2, 5):
                continue

            prev_close_min = np.min(prev_close[valid])
            prev_rsi_min = np.min(prev_rsi[valid])
            prev_close_max = np.max(prev_close[valid])
            prev_rsi_max = np.max(prev_rsi[valid])

            # 底背离：价格新低 + RSI 未新低
            if close[i] < prev_close_min * 0.98 and rsi[i] > prev_rsi_min:
                weekly.iloc[i, weekly.columns.get_loc("rsi_bottom_divergence")] = 1

            # 顶背离：价格新高 + RSI 未新高
            if close[i] > prev_close_max * 1.02 and rsi[i] < prev_rsi_max:
                weekly.iloc[i, weekly.columns.get_loc("rsi_top_divergence")] = 1

        return weekly

    # ═══════════════════════════════════════════════════════════════
    # 信号生成
    # ═══════════════════════════════════════════════════════════════

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        n = len(df)

        rsi_period = int(params.get("rsi_period", 14))
        rsi_oversold = int(params.get("rsi_oversold", 35))
        rsi_overbought = int(params.get("rsi_overbought", 65))
        lookback = int(params.get("divergence_lookback", 20))

        # 初始化信号列
        df["buy_signal"] = 0
        df["sell_signal"] = 0
        df["signal_grade"] = "NONE"
        df["signal_grade_label"] = ""
        df["is_enhanced"] = False
        df["weekly_rsi"] = np.nan

        # resample 日线 → 周线
        try:
            weekly = self._resample_weekly(df)
        except Exception:
            return df

        min_weekly_bars = max(rsi_period + 2, lookback + 2, 10)
        if len(weekly) < min_weekly_bars:
            return df

        # 计算周线 RSI
        weekly = calculate_rsi(weekly, period=rsi_period)
        if "rsi" not in weekly.columns:
            return df

        # 检测背离
        weekly = self._detect_divergence(weekly, lookback)

        # ── 逐周判定信号 ──
        weekly_buy_dates = []
        weekly_sell_dates = []

        rsi_vals = weekly["rsi"].values
        for i in range(lookback, len(weekly)):
            rsi_now = rsi_vals[i]
            rsi_prev = rsi_vals[i - 1]
            if pd.isna(rsi_now) or pd.isna(rsi_prev):
                continue

            bottom_div = weekly["rsi_bottom_divergence"].iloc[i] == 1
            top_div = weekly["rsi_top_divergence"].iloc[i] == 1

            # 买入：RSI 从超卖线下反弹至上方 + 近期（4周内）有底背离确认
            recent_divergence = any(
                weekly["rsi_bottom_divergence"].iloc[max(0, i-3):i+1] == 1
            )
            if rsi_prev < rsi_oversold and rsi_now >= rsi_oversold and recent_divergence:
                weekly_buy_dates.append(weekly.index[i])

            # 卖出（任一触发，均为交叉事件，非持续状态）
            sell_triggered = False
            # 1) RSI 从超买线上方回落（交叉下穿）
            if rsi_prev >= rsi_overbought and rsi_now < rsi_overbought:
                sell_triggered = True
            # 2) 顶背离确认
            if top_div:
                sell_triggered = True
            # 3) RSI 从上方跌破 50 中轴（交叉下穿）
            if rsi_prev >= self.RSI_MIDLINE and rsi_now < self.RSI_MIDLINE:
                sell_triggered = True

            if sell_triggered:
                weekly_sell_dates.append(weekly.index[i])

        # ── 将周线信号映射回日线 ──
        # 构建日线日期索引
        if "_date" not in df.columns:
            df["_date"] = pd.to_datetime(df["date"], errors="coerce")
        df_dates = pd.to_datetime(df["_date"])

        # 将周线 RSI 值复制到该周每日行（便于前端显示）
        for week_date in weekly.index:
            # 找到该周对应日线行：week_date 及之前 5 个交易日
            week_mask = (df_dates <= week_date) & (df_dates > week_date - pd.Timedelta(days=7))
            df.loc[week_mask, "weekly_rsi"] = weekly.loc[week_date, "rsi"] if pd.notna(weekly.loc[week_date, "rsi"]) else np.nan

        # 映射买入信号：每个周线买入日期 → 该周五对应的日线行
        for wd in weekly_buy_dates:
            mask = (df_dates <= wd) & (df_dates > wd - pd.Timedelta(days=7))
            matching = df.index[mask]
            if len(matching) > 0:
                idx = matching[-1]  # 该周最后一个交易日（周五或最近交易日）
                if df.loc[idx, "sell_signal"] != 1:  # 不同时标记买卖
                    df.loc[idx, "buy_signal"] = 1
                    df.loc[idx, "signal_grade"] = "B"
                    df.loc[idx, "signal_grade_label"] = "B级-周线RSI买入"
                    df.loc[idx, "is_enhanced"] = True

        # 映射卖出信号
        for wd in weekly_sell_dates:
            mask = (df_dates <= wd) & (df_dates > wd - pd.Timedelta(days=7))
            matching = df.index[mask]
            if len(matching) > 0:
                idx = matching[-1]
                if df.loc[idx, "buy_signal"] != 1:
                    df.loc[idx, "sell_signal"] = 1
                    df.loc[idx, "signal_grade"] = "B"
                    df.loc[idx, "signal_grade_label"] = "B级-周线RSI卖出"
                    df.loc[idx, "is_enhanced"] = True

        return df

    def create_signal(self, symbol: str, name: str, df: pd.DataFrame,
                      idx: int, params: dict) -> Optional[Signal]:
        if idx < 0 or idx >= len(df):
            return None

        row = df.iloc[idx]
        grade = str(row.get("signal_grade", "NONE"))

        if grade == "NONE" or pd.isna(row.get("signal_grade")):
            return None

        signal_type = "BUY" if row.get("buy_signal") == 1 else "SELL"

        weekly_rsi_val = float(row.get("weekly_rsi")) if pd.notna(row.get("weekly_rsi")) else None

        # 信号描述
        if signal_type == "BUY":
            description = "周线RSI底背离买入：RSI从超卖区反弹，价格新低但动能未跟随，中期底部信号"
        else:
            description = "周线RSI卖出：超买回落/顶背离/跌破中轴，中期动能转弱"

        return Signal(
            symbol=symbol,
            name=name,
            date=str(row.get("date", "")),
            signal_type=signal_type,
            price=float(row["close"]),
            strategy_id=self.strategy_id,
            volume_ratio=float(row.get("volume_ratio", 1.0)) if pd.notna(row.get("volume_ratio")) else None,
            is_enhanced=bool(row.get("is_enhanced", False)),
            metadata={
                "signal_grade": grade,
                "signal_grade_label": str(row.get("signal_grade_label", "")),
                "weekly_rsi": round(weekly_rsi_val, 2) if weekly_rsi_val is not None else None,
                "description": description,
            },
        )
