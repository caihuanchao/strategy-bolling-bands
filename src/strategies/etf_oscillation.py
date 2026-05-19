"""ETF 震荡波段策略 — 布林带 + RSI 均值回归 + K 线形态确认 + 失效预警"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal
from src.indicators import calculate_rsi, calculate_adx, calculate_atr, detect_candlestick_patterns


class EtfOscillationStrategy(StrategyBase):
    """ETF 震荡波段策略：先判环境 → 再找信号 → 失效预警，专为 ETF 震荡市设计"""

    strategy_id = "etf_oscillation"
    strategy_name = "ETF震荡波段"

    # ── 内部常量 ──
    BB_N = 20
    BB_M = 2.5
    RSI_PERIOD = 14
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 65
    ADX_THRESHOLD = 25
    ATR_PERIOD = 14
    MA20_WINDOW = 20
    MA60_WINDOW = 60

    # 环境判定阈值
    MA_FLAT_THRESHOLD = 0.005   # MA 5日斜率 < 0.5%
    RANGE_TOUCH_MIN = 3         # 至少 3 次触及
    RANGE_LOOKBACK = 60         # 箱体检测回溯窗口
    RANGE_TOUCH_PCT = 0.02      # 触及判定容差 2%

    # 失效预警
    BW_LOOKBACK = 20            # 带宽最高检测窗口
    MA_DIVERGE_THRESHOLD = 0.01 # MA 发散阈值 1%

    def get_default_params(self) -> dict:
        return {
            "bb_n": 20,
            "bb_m": 2.5,
            "rsi_period": 14,
            "rsi_oversold": 35,
            "rsi_overbought": 65,
            "adx_threshold": 25,
        }

    def get_params_schema(self) -> list:
        return [
            {"key": "bb_n", "label": "布林带周期 N", "min": 10, "max": 30, "step": 5, "default": 20},
            {"key": "bb_m", "label": "布林带倍数 M", "min": 1.5, "max": 3.0, "step": 0.25, "default": 2.5},
            {"key": "rsi_period", "label": "RSI 周期", "min": 9, "max": 21, "step": 2, "default": 14},
            {"key": "rsi_oversold", "label": "RSI 超卖阈值", "min": 25, "max": 40, "step": 5, "default": 35},
            {"key": "rsi_overbought", "label": "RSI 超买阈值", "min": 60, "max": 75, "step": 5, "default": 65},
            {"key": "adx_threshold", "label": "ADX 趋势阈值", "min": 20, "max": 30, "step": 5, "default": 25},
        ]

    def get_presets(self) -> list:
        return [
            {
                "id": "etf_standard",
                "label": "ETF 标准",
                "params": {"bb_n": 20, "bb_m": 2.5, "rsi_period": 14,
                           "rsi_oversold": 35, "rsi_overbought": 65, "adx_threshold": 25},
                "desc": "宽基 ETF 标准参数（宽轨 2.5 + RSI 35/65），适合中等波动品种",
            },
            {
                "id": "etf_wide",
                "label": "宽轨保守",
                "params": {"bb_n": 20, "bb_m": 3.0, "rsi_period": 14,
                           "rsi_oversold": 30, "rsi_overbought": 70, "adx_threshold": 25},
                "desc": "更宽轨 + 更极端 RSI，减少假信号，适合高波动品种",
            },
            {
                "id": "etf_narrow",
                "label": "窄轨积极",
                "params": {"bb_n": 15, "bb_m": 2.0, "rsi_period": 9,
                           "rsi_oversold": 40, "rsi_overbought": 60, "adx_threshold": 20},
                "desc": "窄轨 + 敏感 RSI，更快捕捉信号，适合低波动红利 ETF",
            },
        ]

    def get_optimizable_params(self) -> list:
        from src.optimizer import OptimizableParam
        return [
            OptimizableParam(key="bb_n", label="布林带周期 N", type="int",
                             min=10, max=30, step=5, default=20),
            OptimizableParam(key="bb_m", label="布林带倍数 M", type="float",
                             min=1.5, max=3.0, step=0.25, default=2.5),
            OptimizableParam(key="rsi_period", label="RSI 周期", type="int",
                             min=9, max=21, step=2, default=14),
            OptimizableParam(key="rsi_oversold", label="RSI 超卖阈值", type="int",
                             min=25, max=40, step=5, default=35),
            OptimizableParam(key="rsi_overbought", label="RSI 超买阈值", type="int",
                             min=60, max=75, step=5, default=65),
            OptimizableParam(key="adx_threshold", label="ADX 趋势阈值", type="int",
                             min=20, max=30, step=5, default=25),
        ]

    # ═══════════════════════════════════════════════════════════════
    # Phase 0: 指标准备
    # ═══════════════════════════════════════════════════════════════

    def _ensure_indicators(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """幂等补充所有需要的指标列"""
        if params is None:
            params = {}
        df = df.copy()

        bb_n = int(params.get("bb_n", self.BB_N))
        bb_m = float(params.get("bb_m", self.BB_M))
        rsi_period = int(params.get("rsi_period", self.RSI_PERIOD))

        # 布林带
        if "ma_mid" not in df.columns:
            df["ma_mid"] = df["close"].rolling(window=bb_n).mean()
        if "std" not in df.columns:
            df["std"] = df["close"].rolling(window=bb_n).std()
        if "boll_up" not in df.columns:
            df["boll_up"] = df["ma_mid"] + bb_m * df["std"]
            df["boll_down"] = df["ma_mid"] - bb_m * df["std"]

        # 带宽
        if "bandwidth" not in df.columns:
            df["bandwidth"] = np.where(
                df["ma_mid"] > 0,
                (df["boll_up"] - df["boll_down"]) / df["ma_mid"] * 100,
                np.nan,
            )

        # RSI
        if "rsi" not in df.columns:
            df = calculate_rsi(df, period=rsi_period)

        # ADX
        if "adx" not in df.columns:
            df = calculate_adx(df, period=self.ATR_PERIOD)

        # ATR
        if "atr" not in df.columns:
            df = calculate_atr(df, period=self.ATR_PERIOD)

        # 均线
        if "ma20" not in df.columns:
            df["ma20"] = df["close"].rolling(window=self.MA20_WINDOW).mean()
        if "ma60" not in df.columns:
            df["ma60"] = df["close"].rolling(window=self.MA60_WINDOW).mean()

        # 成交量
        if "volume" not in df.columns:
            df["volume"] = 0
        df["avg_volume"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = np.where(
            df["avg_volume"] > 0,
            df["volume"] / df["avg_volume"],
            1.0,
        )

        # K 线形态
        if "pattern_bullish" not in df.columns:
            df = detect_candlestick_patterns(df)

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: 环境检测
    # ═══════════════════════════════════════════════════════════════

    def _detect_environment(self, df: pd.DataFrame) -> pd.DataFrame:
        """判定震荡/过渡/趋势三大环境"""
        n = len(df)
        df["environment"] = "unknown"
        df["env_label"] = "未知"

        min_bars = max(self.RANGE_LOOKBACK, self.MA60_WINDOW + 10)
        if n < min_bars:
            return df

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        ma20 = df["ma20"].values
        ma60 = df["ma60"].values
        atr = df["atr"].values

        for i in range(min_bars, n):
            if pd.isna(ma20[i]) or pd.isna(ma60[i]) or pd.isna(close[i]):
                continue

            # ── 条件1: MA20 走平 ──
            ma_flat = False
            if i >= 5 and pd.notna(ma20[i - 5]) and ma20[i - 5] > 0:
                slope_20 = (ma20[i] - ma20[i - 5]) / ma20[i - 5]
                ma_flat = abs(slope_20) < self.MA_FLAT_THRESHOLD

            # ── 条件2: 箱体确认 ──
            range_confirmed = False
            if i >= self.RANGE_LOOKBACK:
                slice_high = high[i - self.RANGE_LOOKBACK:i]
                slice_low = low[i - self.RANGE_LOOKBACK:i]
                valid_hi = slice_high[~np.isnan(slice_high)]
                valid_lo = slice_low[~np.isnan(slice_low)]
                if len(valid_hi) > 30 and len(valid_lo) > 30:
                    range_top = np.max(valid_hi)
                    range_bottom = np.min(valid_lo)
                    if range_top > range_bottom:
                        touches_top = np.sum(valid_hi >= range_top * (1 - self.RANGE_TOUCH_PCT))
                        touches_bottom = np.sum(valid_lo <= range_bottom * (1 + self.RANGE_TOUCH_PCT))
                        range_confirmed = (touches_top >= self.RANGE_TOUCH_MIN and
                                           touches_bottom >= self.RANGE_TOUCH_MIN)

            # ── 条件3: ATR 稳定或下降 ──
            atr_stable_or_declining = False
            if i >= 5 and pd.notna(atr[i]) and pd.notna(atr[i - 5]) and atr[i - 5] > 0:
                atr_change = atr[i] / atr[i - 5]
                atr_stable_or_declining = atr_change < 1.15  # 不扩张即可

            # ── 信号: MA 斜率较大 → 趋势 ──
            is_trending = False
            if i >= 5 and pd.notna(ma20[i - 5]) and ma20[i - 5] > 0:
                slope_20 = (ma20[i] - ma20[i - 5]) / ma20[i - 5]
                # ATR 扩张 + MA 有明显斜率
                if abs(slope_20) > 0.01 and pd.notna(atr[i]) and pd.notna(atr[i - 5]) and atr[i - 5] > 0:
                    is_trending = atr[i] / atr[i - 5] > 1.2

            conditions_met = sum([ma_flat, range_confirmed, atr_stable_or_declining])

            if conditions_met >= 3:
                env = "oscillation"
                env_label = "震荡格局"
            elif is_trending:
                env = "trend"
                env_label = "趋势行情"
            elif conditions_met >= 2:
                env = "transition"
                env_label = "震荡过渡"
            elif conditions_met >= 1:
                env = "transition"
                env_label = "震荡偏弱"
            else:
                env = "trend"
                env_label = "趋势行情"

            df.loc[df.index[i], "environment"] = env
            df.loc[df.index[i], "env_label"] = env_label

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: 信号生成
    # ═══════════════════════════════════════════════════════════════

    def _generate_signals(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """仅在震荡环境中生成 BB+RSI 信号，K 线形态增强等级"""
        if params is None:
            params = {}
        n = len(df)

        df["buy_signal"] = 0
        df["sell_signal"] = 0
        df["signal_grade"] = "NONE"
        df["signal_grade_label"] = ""
        df["is_enhanced"] = False

        rsi_oversold = int(params.get("rsi_oversold", self.RSI_OVERSOLD))
        rsi_overbought = int(params.get("rsi_overbought", self.RSI_OVERBOUGHT))

        min_bars = max(self.RANGE_LOOKBACK, self.MA60_WINDOW + 10)
        for i in range(min_bars, n):
            if df["environment"].iloc[i] != "oscillation":
                continue

            close_val = df["close"].iloc[i]
            boll_up = df["boll_up"].iloc[i]
            boll_down = df["boll_down"].iloc[i]
            rsi_val = df["rsi"].iloc[i]

            if pd.isna(close_val) or pd.isna(boll_up) or pd.isna(boll_down) or pd.isna(rsi_val):
                continue

            bb_touch_lower = close_val <= boll_down
            bb_touch_upper = close_val >= boll_up
            rsi_low = rsi_val <= rsi_oversold
            rsi_high = rsi_val >= rsi_overbought

            pattern_bullish = df["pattern_bullish"].iloc[i] == 1
            pattern_bearish = df["pattern_bearish"].iloc[i] == 1

            # ── 做多 ──
            if bb_touch_lower and rsi_low:
                grade = "B"
                if pattern_bullish:
                    grade = "A"
                df.loc[df.index[i], "buy_signal"] = 1
                df.loc[df.index[i], "signal_grade"] = grade
                df.loc[df.index[i], "signal_grade_label"] = _grade_label(grade)
                df.loc[df.index[i], "is_enhanced"] = grade == "A"

            # ── 做空 ──
            if bb_touch_upper and rsi_high:
                grade = "B"
                if pattern_bearish:
                    grade = "A"
                df.loc[df.index[i], "sell_signal"] = 1
                df.loc[df.index[i], "signal_grade"] = grade
                df.loc[df.index[i], "signal_grade_label"] = _grade_label(grade)
                df.loc[df.index[i], "is_enhanced"] = grade == "A"

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 3: 失效预警
    # ═══════════════════════════════════════════════════════════════

    def _detect_failure_warnings(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """检测震荡环境失效信号，触发即生成卖出信号"""
        if params is None:
            params = {}
        n = len(df)

        adx_threshold = int(params.get("adx_threshold", self.ADX_THRESHOLD))

        min_bars = max(self.BW_LOOKBACK, self.MA60_WINDOW + 10)
        for i in range(min_bars, n):
            if df["environment"].iloc[i] != "oscillation":
                continue

            failure = 0

            # 1. 布林带宽 20 日最高 → 突破在即
            bw = df["bandwidth"].iloc[i]
            bw_slice = df["bandwidth"].iloc[i - self.BW_LOOKBACK:i]
            bw_valid = bw_slice[~np.isnan(bw_slice)]
            if len(bw_valid) >= 15 and pd.notna(bw) and bw >= np.max(bw_valid):
                failure += 1

            # 2. ADX 从 < 20 突破阈值 → 趋势确认
            adx_now = df["adx"].iloc[i]
            adx_prev = df["adx"].iloc[i - 5] if i >= 5 else adx_now
            if pd.notna(adx_now) and pd.notna(adx_prev):
                if adx_now > adx_threshold and adx_prev < 20:
                    failure += 1

            # 3. MA20/MA60 从缠绕转为发散
            if i >= 5 and pd.notna(df["ma20"].iloc[i]) and pd.notna(df["ma60"].iloc[i]):
                if df["ma20"].iloc[i - 5] > 0 and df["ma60"].iloc[i - 5] > 0:
                    slope_20 = (df["ma20"].iloc[i] - df["ma20"].iloc[i - 5]) / df["ma20"].iloc[i - 5]
                    slope_60 = (df["ma60"].iloc[i] - df["ma60"].iloc[i - 5]) / df["ma60"].iloc[i - 5]
                    if abs(slope_20 - slope_60) > self.MA_DIVERGE_THRESHOLD:
                        failure += 1

            if failure >= 1 and df.loc[df.index[i], "buy_signal"] != 1:
                df.loc[df.index[i], "sell_signal"] = 1
                df.loc[df.index[i], "signal_grade"] = "FAILURE"
                df.loc[df.index[i], "signal_grade_label"] = "失效预警-离场"
                df.loc[df.index[i], "is_enhanced"] = False

        return df

    # ═══════════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════════

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = self._ensure_indicators(df, params)
        df = self._detect_environment(df)
        df = self._generate_signals(df, params)
        df = self._detect_failure_warnings(df, params)
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

        def _f(val, default=None):
            try:
                v = float(val)
                return round(v, 4) if pd.notna(v) and not np.isinf(v) else default
            except (ValueError, TypeError):
                return default

        close_val = _f(row.get("close"), 0)
        rsi_val = _f(row.get("rsi"))
        boll_up = _f(row.get("boll_up"))
        boll_mid = _f(row.get("ma_mid"))
        boll_down = _f(row.get("boll_down"))
        bandwidth = _f(row.get("bandwidth"))
        adx_val = _f(row.get("adx"))
        atr_val = _f(row.get("atr"))
        vol_ratio = _f(row.get("volume_ratio"))
        env = str(row.get("environment", "unknown"))
        env_label = str(row.get("env_label", "未知"))

        # 入场条件摘要
        entry_conditions = {
            "environment": env,
            "environment_label": env_label,
            "bb_touch_lower": bool(row.get("close", 0) <= row.get("boll_down", 0)),
            "bb_touch_upper": bool(row.get("close", 0) >= row.get("boll_up", 0)),
            "rsi_oversold": rsi_val is not None and rsi_val <= 35,
            "rsi_overbought": rsi_val is not None and rsi_val >= 65,
            "pattern_hammer": bool(row.get("pattern_hammer")),
            "pattern_bullish_engulfing": bool(row.get("pattern_bullish_engulfing")),
            "pattern_shooting_star": bool(row.get("pattern_shooting_star")),
            "pattern_bearish_engulfing": bool(row.get("pattern_bearish_engulfing")),
        }

        return Signal(
            symbol=symbol,
            name=name,
            date=str(row.get("date", "")),
            signal_type=signal_type,
            price=close_val,
            strategy_id=self.strategy_id,
            volume_ratio=vol_ratio,
            is_enhanced=bool(row.get("is_enhanced", False)),
            metadata={
                "signal_grade": grade,
                "signal_grade_label": str(row.get("signal_grade_label", "")),
                "environment": env,
                "environment_label": env_label,
                "rsi": round(rsi_val, 2) if rsi_val is not None else None,
                "boll_up": round(boll_up, 2) if boll_up is not None else None,
                "boll_mid": round(boll_mid, 2) if boll_mid is not None else None,
                "boll_down": round(boll_down, 2) if boll_down is not None else None,
                "bandwidth": round(bandwidth, 2) if bandwidth is not None else None,
                "adx": round(adx_val, 2) if adx_val is not None else None,
                "atr": round(atr_val, 2) if atr_val is not None else None,
                "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
                "entry_conditions": entry_conditions,
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "signal_grade_label", "label": "信号等级", "format": "text"},
                    {"key": "environment_label", "label": "市场环境", "format": "text"},
                    {"key": "rsi", "label": "RSI", "format": "text"},
                    {"key": "adx", "label": "ADX", "format": "text"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                ],
            },
        )


def _grade_label(grade: str) -> str:
    if grade.startswith("A"):
        return "A级-增强信号"
    if grade.startswith("B"):
        return "B级-基础信号"
    if grade.startswith("FAILURE"):
        return "失效预警-离场"
    return grade
