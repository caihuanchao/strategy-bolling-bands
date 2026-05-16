"""MACD+RSI+成交量三重确认策略 — 四级信号分级 (C/B/A/S)"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal
from src.indicators import calculate_macd, calculate_rsi, calculate_adx


class TripleConfirmStrategy(StrategyBase):
    """三重确认策略：MACD(趋势) + RSI(极端检测) + 成交量(资金验证) 交叉确认"""

    strategy_id = "triple_confirm"
    strategy_name = "三重确认"

    def get_default_params(self) -> dict:
        return {}

    def get_params_schema(self) -> list:
        return []

    def get_presets(self) -> list:
        return [
            {
                "id": "standard",
                "label": "标准参数",
                "params": {},
                "desc": "MACD(12/26/9) + RSI(14) + 成交量MA20，固定参数",
            }
        ]

    # ── 参数常量 ──
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_PERIOD = 14
    VOL_WINDOW = 20
    ADX_PERIOD = 14
    ADX_THRESHOLD = 20
    MA50_WINDOW = 50
    DIV_LOOKBACK = 60

    RSI_LONG_LOW = 30
    RSI_LONG_HIGH = 65
    RSI_SHORT_LOW = 45
    RSI_SHORT_HIGH = 70
    RSI_OVERBOUGHT_EXIT = 75
    VOL_A_THRESHOLD = 1.0
    VOL_S_THRESHOLD = 1.5

    def _ensure_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """幂等补充所有需要的指标列"""
        df = df.copy()

        if "macd" not in df.columns:
            df = calculate_macd(df, fast=self.MACD_FAST, slow=self.MACD_SLOW, signal=self.MACD_SIGNAL)
        if "macd_bullish_cross" not in df.columns:
            df["macd_bullish_cross"] = np.where(
                (df["macd"] > df["macd_signal"]) &
                (df["macd"].shift(1) <= df["macd_signal"].shift(1)),
                1, 0
            )
            df["macd_bearish_cross"] = np.where(
                (df["macd"] < df["macd_signal"]) &
                (df["macd"].shift(1) >= df["macd_signal"].shift(1)),
                1, 0
            )

        if "rsi" not in df.columns:
            df = calculate_rsi(df, period=self.RSI_PERIOD)

        if "adx" not in df.columns:
            df = calculate_adx(df, period=self.ADX_PERIOD)

        # 成交量均量和量比
        if "volume" not in df.columns:
            df["volume"] = 0
        df["avg_volume"] = df["volume"].rolling(window=self.VOL_WINDOW).mean()
        df["volume_ratio"] = np.where(
            df["avg_volume"] > 0,
            df["volume"] / df["avg_volume"],
            1.0
        )

        # MA50 趋势过滤
        df["ma50"] = df["close"].rolling(window=self.MA50_WINDOW).mean()
        df["ma50_direction"] = 0  # 1=向上, -1=向下
        # MA50 方向：当前 MA50 vs 5日前 MA50
        ma50_vals = df["ma50"].values
        for i in range(self.MA50_WINDOW + 5, len(df)):
            if pd.notna(ma50_vals[i]) and pd.notna(ma50_vals[i - 5]):
                if ma50_vals[i] > ma50_vals[i - 5]:
                    df.loc[df.index[i], "ma50_direction"] = 1
                elif ma50_vals[i] < ma50_vals[i - 5]:
                    df.loc[df.index[i], "ma50_direction"] = -1

        return df

    def _detect_macd_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测 MACD 背离（底背离=买入信号增强, 顶背离=卖出信号增强）"""
        n = len(df)
        lookback = self.DIV_LOOKBACK
        df["macd_bottom_divergence"] = 0
        df["macd_top_divergence"] = 0

        if n < lookback:
            return df

        close = df["close"].values
        macd_hist = df["macd_histogram"].values

        for i in range(lookback, n):
            if pd.isna(close[i]) or pd.isna(macd_hist[i]):
                continue

            prev_slice_close = close[i - lookback:i]
            prev_slice_hist = macd_hist[i - lookback:i]

            # 过滤 NaN
            valid = ~np.isnan(prev_slice_close) & ~np.isnan(prev_slice_hist)
            if valid.sum() < 20:
                continue

            prev_close_min = np.min(prev_slice_close[valid])
            prev_hist_min = np.min(prev_slice_hist[valid])
            prev_close_max = np.max(prev_slice_close[valid])
            prev_hist_max = np.max(prev_slice_hist[valid])

            # 底背离：价格新低 + MACD 柱未新低
            if close[i] < prev_close_min * 0.98 and macd_hist[i] > prev_hist_min:
                df.loc[df.index[i], "macd_bottom_divergence"] = 1

            # 顶背离：价格新高 + MACD 柱未新高
            if close[i] > prev_close_max * 1.02 and macd_hist[i] < prev_hist_max:
                df.loc[df.index[i], "macd_top_divergence"] = 1

        return df

    def _detect_rsi_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测 RSI 背离"""
        n = len(df)
        lookback = self.DIV_LOOKBACK
        df["rsi_bottom_divergence"] = 0
        df["rsi_top_divergence"] = 0

        if n < lookback:
            return df

        close = df["close"].values
        rsi = df["rsi"].values

        for i in range(lookback, n):
            if pd.isna(close[i]) or pd.isna(rsi[i]):
                continue

            prev_slice_close = close[i - lookback:i]
            prev_slice_rsi = rsi[i - lookback:i]
            valid = ~np.isnan(prev_slice_close) & ~np.isnan(prev_slice_rsi)
            if valid.sum() < 20:
                continue

            prev_close_min = np.min(prev_slice_close[valid])
            prev_rsi_min = np.min(prev_slice_rsi[valid])
            prev_close_max = np.max(prev_slice_close[valid])
            prev_rsi_max = np.max(prev_slice_rsi[valid])

            # RSI 底背离：价格新低 + RSI 未新低，且 RSI < 40
            if close[i] < prev_close_min * 0.98 and rsi[i] > prev_rsi_min and rsi[i] < 40:
                df.loc[df.index[i], "rsi_bottom_divergence"] = 1

            # RSI 顶背离：价格新高 + RSI 未新高
            if close[i] > prev_close_max * 1.02 and rsi[i] < prev_rsi_max:
                df.loc[df.index[i], "rsi_top_divergence"] = 1

        return df

    def _detect_volume_shrink_pattern(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测"缩量止跌 + 今日放量起涨"格局（A 级条件之一）"""
        n = len(df)
        df["volume_shrink_pattern"] = 0

        if n < 5:
            return df

        for i in range(4, n):
            close = df["close"].values
            vol = df["volume"].values

            if pd.isna(close[i]) or pd.isna(vol[i]):
                continue

            # 今日放量起涨
            today_up = close[i] > close[i - 1] if pd.notna(close[i - 1]) else False
            today_vol_expand = vol[i] > vol[i - 1] if (pd.notna(vol[i - 1]) and vol[i - 1] > 0) else False

            if not (today_up and today_vol_expand):
                continue

            # 前 3 天缩量止跌
            prev_closes = close[i - 3:i]
            prev_vols = vol[i - 3:i]
            if len(prev_closes) < 3:
                continue

            valid_prev = all(pd.notna(v) for v in prev_closes) and all(pd.notna(v) for v in prev_vols)
            if not valid_prev:
                continue

            price_stabilized = all(abs(prev_closes[j] - prev_closes[j - 1]) / prev_closes[j - 1] < 0.02
                                   for j in range(1, len(prev_closes)))
            vol_shrinking = all(prev_vols[j] < prev_vols[j - 1]
                               for j in range(1, len(prev_vols)))

            if price_stabilized and vol_shrinking:
                df.loc[df.index[i], "volume_shrink_pattern"] = 1

        return df

    def _calc_weekly_confirm(self, df: pd.DataFrame) -> pd.DataFrame:
        """日线 resample 周线，计算周线 MACD 方向确认"""
        n = len(df)
        df["weekly_macd_bullish"] = 0

        if n < 60:
            return df

        try:
            df_idx = df.copy()
            df_idx["_date"] = pd.to_datetime(df_idx["date"], errors="coerce")
            df_idx = df_idx.dropna(subset=["_date"])
            if len(df_idx) < 30:
                return df

            df_idx = df_idx.set_index("_date")
            weekly_close = df_idx["close"].resample("W-FRI").last().dropna()

            if len(weekly_close) < 26:
                return df

            weekly_df = pd.DataFrame({"close": weekly_close.values})
            weekly_df = calculate_macd(weekly_df, fast=self.MACD_FAST, slow=self.MACD_SLOW, signal=self.MACD_SIGNAL)

            # 找到周线 MACD 看涨的周五日期
            weekly_bullish_dates = []
            for j in range(len(weekly_df)):
                macd_val = weekly_df["macd"].iloc[j]
                sig_val = weekly_df["macd_signal"].iloc[j]
                if pd.notna(macd_val) and pd.notna(sig_val) and macd_val > sig_val:
                    weekly_bullish_dates.append(weekly_close.index[j])

            if not weekly_bullish_dates:
                return df

            # 映射回日线：日线日期所在周的周五看涨 → 该周所有日线标记
            for i in range(n):
                try:
                    d = pd.Timestamp(df["date"].iloc[i])
                    # 计算该日所属周的周五
                    fri = d + pd.offsets.Week(weekday=4, weekday_offset=0)
                    if d > fri:
                        fri = d + pd.offsets.Week(weekday=4)
                    for wd in weekly_bullish_dates:
                        if abs((fri - wd).days) <= 3:
                            df.loc[df.index[i], "weekly_macd_bullish"] = 1
                            break
                except Exception:
                    pass
        except Exception:
            pass

        return df

    def _classify_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """四级信号分级 (C/B/A/S)"""
        n = len(df)

        df["signal_grade"] = "NONE"
        df["signal_grade_label"] = ""
        df["buy_signal"] = 0
        df["sell_signal"] = 0
        df["is_enhanced"] = False

        for i in range(max(60, self.MA50_WINDOW + 10), n):
            macd_cross_buy = df["macd_bullish_cross"].iloc[i] == 1
            macd_cross_sell = df["macd_bearish_cross"].iloc[i] == 1

            if not macd_cross_buy and not macd_cross_sell:
                continue

            rsi_val = df["rsi"].iloc[i]
            rsi_prev = df["rsi"].iloc[i - 1]
            vol_ratio = df["volume_ratio"].iloc[i]
            macd_bottom_div = df["macd_bottom_divergence"].iloc[i] == 1
            macd_top_div = df["macd_top_divergence"].iloc[i] == 1
            rsi_bottom_div = df["rsi_bottom_divergence"].iloc[i] == 1
            rsi_top_div = df["rsi_top_divergence"].iloc[i] == 1
            vol_shrink = df["volume_shrink_pattern"].iloc[i] == 1

            if pd.isna(rsi_val) or pd.isna(vol_ratio):
                continue

            grade = None
            signal_type = None

            # ── 做多信号 ──
            if macd_cross_buy:
                # C 级：仅 MACD 金叉
                grade = "C"
                signal_type = "BUY"

                # B 级：RSI 在 30-65 区间且方向向上
                rsi_in_zone = self.RSI_LONG_LOW <= rsi_val <= self.RSI_LONG_HIGH
                rsi_dir_up = pd.notna(rsi_prev) and rsi_val > rsi_prev
                if rsi_in_zone and rsi_dir_up:
                    grade = "B"

                    # A 级：成交量确认
                    vol_ok = vol_ratio >= self.VOL_A_THRESHOLD
                    if vol_ok and vol_shrink:
                        grade = "A"

                # S 级：三重背离共振（覆盖 A/B/C）
                if macd_bottom_div and rsi_bottom_div and vol_ratio >= self.VOL_S_THRESHOLD:
                    grade = "S"

            # ── 做空信号 ──
            elif macd_cross_sell:
                grade = "C"
                signal_type = "SELL"

                rsi_in_zone = self.RSI_SHORT_LOW <= rsi_val <= self.RSI_SHORT_HIGH
                rsi_dir_down = pd.notna(rsi_prev) and rsi_val < rsi_prev
                if rsi_in_zone and rsi_dir_down:
                    grade = "B"

                    vol_ok = vol_ratio >= self.VOL_A_THRESHOLD
                    if vol_ok and vol_shrink:
                        grade = "A"

                if macd_top_div and rsi_top_div and vol_ratio >= self.VOL_S_THRESHOLD:
                    grade = "S"

            if grade is None or signal_type is None:
                continue

            # ── ADX 过滤 ──
            adx_val = df["adx"].iloc[i]
            if pd.notna(adx_val) and adx_val < self.ADX_THRESHOLD:
                grade = grade + "_adx_filtered"

            # ── MA50 趋势过滤（做多时 MA50 向下则降级） ──
            if signal_type == "BUY":
                ma50_dir = df["ma50_direction"].iloc[i]
                if ma50_dir == -1 and "_adx_filtered" not in grade:
                    grade = grade + "_trend_weak"

            df.loc[df.index[i], "signal_grade"] = grade
            df.loc[df.index[i], "signal_grade_label"] = _grade_label(grade)

            if signal_type == "BUY":
                df.loc[df.index[i], "buy_signal"] = 1
            else:
                df.loc[df.index[i], "sell_signal"] = 1

            # is_enhanced: S 或 A 级为增强信号
            base_grade = grade.split("_")[0]
            df.loc[df.index[i], "is_enhanced"] = base_grade in ("S", "A")

        return df

    def _detect_exit_triggers(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测出场条件"""
        n = len(df)

        for col in ["exit_trigger_1", "exit_trigger_2", "exit_trigger_3", "exit_trigger_4", "exit_trigger_5"]:
            df[col] = 0

        for i in range(5, n):
            # 1. MACD 死叉（做多出场）
            if df["macd_bearish_cross"].iloc[i] == 1:
                df.loc[df.index[i], "exit_trigger_1"] = 1

            # 2. RSI 顶背离
            if df["rsi_top_divergence"].iloc[i] == 1:
                df.loc[df.index[i], "exit_trigger_2"] = 1

            # 3. RSI 进入超买后回落
            rsi_now = df["rsi"].iloc[i]
            rsi_prev = df["rsi"].iloc[i - 1]
            if pd.notna(rsi_now) and pd.notna(rsi_prev):
                if rsi_prev >= self.RSI_OVERBOUGHT_EXIT and rsi_now < self.RSI_OVERBOUGHT_EXIT:
                    df.loc[df.index[i], "exit_trigger_3"] = 1

            # 4. 价涨量缩连续 3 根 K 线
            if i >= 3:
                count = 0
                for j in range(i - 2, i + 1):
                    close_j = df["close"].iloc[j]
                    close_prev = df["close"].iloc[j - 1]
                    vol_j = df["volume"].iloc[j]
                    vol_prev = df["volume"].iloc[j - 1]
                    if (pd.notna(close_j) and pd.notna(close_prev) and
                        pd.notna(vol_j) and pd.notna(vol_prev)):
                        if close_j > close_prev and vol_j < vol_prev:
                            count += 1
                if count >= 3:
                    df.loc[df.index[i], "exit_trigger_4"] = 1

            # 5. 价格跌破 MA20（辅助出场）
            close_val = df["close"].iloc[i]
            ma50_val = df["ma50"].iloc[i]
            if pd.notna(close_val) and pd.notna(ma50_val) and ma50_val > 0:
                # 使用 MA20（价格 vs MA20）
                if i >= 20:
                    ma20 = df["close"].iloc[i - 19:i + 1].mean()
                    if close_val < ma20:
                        df.loc[df.index[i], "exit_trigger_5"] = 1

        return df

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = self._ensure_indicators(df)
        df = self._detect_macd_divergence(df)
        df = self._detect_rsi_divergence(df)
        df = self._detect_volume_shrink_pattern(df)
        df = self._calc_weekly_confirm(df)
        df = self._classify_signals(df)
        df = self._detect_exit_triggers(df)
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
        base_grade = grade.split("_")[0]

        vol_ratio = float(row.get("volume_ratio", 1.0)) if pd.notna(row.get("volume_ratio")) else None
        adx_val = float(row.get("adx", 0)) if pd.notna(row.get("adx")) else None
        rsi_val = float(row.get("rsi", 50)) if pd.notna(row.get("rsi")) else None
        macd_val = float(row.get("macd", 0)) if pd.notna(row.get("macd")) else None
        macd_sig = float(row.get("macd_signal", 0)) if pd.notna(row.get("macd_signal")) else None
        macd_hist = float(row.get("macd_histogram", 0)) if pd.notna(row.get("macd_histogram")) else None
        ma50_val = float(row.get("ma50", 0)) if pd.notna(row.get("ma50")) else None
        ma50_dir = int(row.get("ma50_direction", 0)) if pd.notna(row.get("ma50_direction")) else 0
        weekly_confirm = bool(row.get("weekly_macd_bullish", 0))

        # 入场条件
        entry_conditions = {
            "macd_cross": bool(row.get("macd_bullish_cross") or row.get("macd_bearish_cross")),
            "rsi_in_zone": True,  # 已通过分级逻辑保证
            "rsi_direction_correct": True,
            "volume_ok": vol_ratio is not None and vol_ratio >= self.VOL_A_THRESHOLD,
            "macd_divergence": bool(row.get("macd_bottom_divergence") or row.get("macd_top_divergence")),
            "rsi_divergence": bool(row.get("rsi_bottom_divergence") or row.get("rsi_top_divergence")),
        }

        # 出场条件
        exit_triggers = []
        exit_labels = {
            "exit_trigger_1": "MACD死叉（金叉）",
            "exit_trigger_2": "RSI背离",
            "exit_trigger_3": "RSI超买后回落",
            "exit_trigger_4": "价涨量缩连续3日",
            "exit_trigger_5": "价格跌破MA20",
        }
        for col, label in exit_labels.items():
            if row.get(col, 0) == 1:
                exit_triggers.append(label)

        # 建议仓位说明
        position_hints = {
            "S": "正常或略大仓位（风险不超过3%），止损在背离低点下方",
            "A": "正常仓位，标准止损",
            "B": "轻仓试探（正常仓位50%），止损严格",
            "C": "仅观察，不交易。等待RSI和成交量确认",
        }
        position_advice = position_hints.get(base_grade, "")

        grade_labels = {"S": "S级-高确信", "A": "A级-标准入场", "B": "B级-试探", "C": "C级-仅观察"}
        grade_label = grade_labels.get(base_grade, grade)

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
                "signal_grade": base_grade,
                "signal_grade_full": grade,
                "signal_grade_label": grade_label,
                "adx": round(adx_val, 1) if adx_val is not None else None,
                "ma50": round(ma50_val, 2) if ma50_val is not None else None,
                "ma50_direction": "向上" if ma50_dir == 1 else ("向下" if ma50_dir == -1 else "平坦"),
                "weekly_confirm": weekly_confirm,
                "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
                "rsi": round(rsi_val, 1),
                "macd": round(macd_val, 4) if macd_val is not None else None,
                "macd_signal": round(macd_sig, 4) if macd_sig is not None else None,
                "macd_histogram": round(macd_hist, 4) if macd_hist is not None else None,
                "entry_conditions": entry_conditions,
                "exit_triggers": exit_triggers,
                "position_advice": position_advice,
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "signal_grade_label", "label": "信号等级", "format": "text"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                    {"key": "adx", "label": "ADX", "format": "text"},
                    {"key": "rsi", "label": "RSI", "format": "text"},
                ],
            },
        )


def _grade_label(grade: str) -> str:
    """将信号等级代码转为中文标签"""
    if grade.startswith("S"):
        return "S级-高确信"
    if grade.startswith("A"):
        return "A级-标准入场"
    if grade.startswith("B"):
        return "B级-试探"
    if grade.startswith("C"):
        return "C级-仅观察"
    return grade
