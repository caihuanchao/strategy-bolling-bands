"""KDJ + 布林带 + ATR 波动率策略 — 环境感知 + 三模式切换 + 四级信号分级 (C/B/A/S)"""

import pandas as pd
import numpy as np
from typing import Optional

from src.strategies import StrategyBase
from src.signals import Signal
from src.indicators import calculate_kdj, calculate_atr


class KdjBollingerAtrStrategy(StrategyBase):
    """KDJ + 布林带 + ATR 波动率策略：先判定环境，再选交易模式"""

    strategy_id = "kdj_bollinger_atr"
    strategy_name = "KDJ+布林带+ATR"

    # ── 参数常量 ──
    BB_N = 20
    BB_M = 2.0
    KDJ_N = 9
    ATR_PERIOD = 14
    MA20_WINDOW = 20
    MA50_WINDOW = 50
    VOL_WINDOW = 20

    # 环境判定
    BB_SLOPE_THRESHOLD = 0.005  # 中轨斜率阈值
    ATR_EXPAND_THRESHOLD = 1.2  # ATR 扩张阈值
    SQUEEZE_LOOKBACK = 120      # Squeeze 回溯期
    SQUEEZE_PERCENTILE = 0.10   # 带宽历史最低 10%

    # KDJ 阈值
    KDJ_OVERBOUGHT_K = 80
    KDJ_OVERBOUGHT_D = 70
    KDJ_OVERBOUGHT_J = 100
    KDJ_OVERSOLD_K = 20
    KDJ_OVERSOLD_D = 30
    KDJ_OVERSOLD_J = 0

    # 成交量
    VOL_A_THRESHOLD = 1.0
    VOL_S_THRESHOLD = 1.3

    # 背离检测
    DIV_LOOKBACK = 60

    def get_default_params(self) -> dict:
        return {}

    def get_params_schema(self) -> list:
        return []

    def get_presets(self) -> list:
        return [
            {
                "id": "standard",
                "label": "经典参数",
                "params": {},
                "desc": "KDJ(9,3,3) + ATR(14) + 布林带(20,2)，固定参数，三环境自适应",
            }
        ]

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: 指标计算
    # ═══════════════════════════════════════════════════════════════

    def _ensure_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """幂等补充所有需要的指标列"""
        df = df.copy()

        if "kdj_k" not in df.columns:
            df = calculate_kdj(df, n=self.KDJ_N)

        if "atr" not in df.columns:
            df = calculate_atr(df, period=self.ATR_PERIOD)

        # 布林带
        if "ma_mid" not in df.columns:
            df["ma_mid"] = df["close"].rolling(window=self.BB_N).mean()
        if "std" not in df.columns:
            df["std"] = df["close"].rolling(window=self.BB_N).std()
        if "boll_up" not in df.columns:
            df["boll_up"] = df["ma_mid"] + self.BB_M * df["std"]
            df["boll_down"] = df["ma_mid"] - self.BB_M * df["std"]

        # 带宽
        if "bandwidth" not in df.columns:
            df["bandwidth"] = np.where(
                df["ma_mid"] > 0,
                (df["boll_up"] - df["boll_down"]) / df["ma_mid"] * 100,
                np.nan,
            )

        # 移动均线
        if "ma20" not in df.columns:
            df["ma20"] = df["close"].rolling(window=self.MA20_WINDOW).mean()
        if "ma50" not in df.columns:
            df["ma50"] = df["close"].rolling(window=self.MA50_WINDOW).mean()

        # 成交量
        if "volume" not in df.columns:
            df["volume"] = 0
        df["avg_volume"] = df["volume"].rolling(window=self.VOL_WINDOW).mean()
        df["volume_ratio"] = np.where(
            df["avg_volume"] > 0,
            df["volume"] / df["avg_volume"],
            1.0,
        )

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: 环境判定
    # ═══════════════════════════════════════════════════════════════

    def _detect_environment(self, df: pd.DataFrame) -> pd.DataFrame:
        """判定三大市场环境：震荡(range) / 趋势(trend) / 蓄势(squeeze)"""
        n = len(df)
        df["environment"] = "unknown"
        df["env_label"] = "未知"

        min_bars = max(self.SQUEEZE_LOOKBACK, self.MA50_WINDOW + 10)
        if n < min_bars:
            return df

        mid = df["ma_mid"].values
        bandwidth = df["bandwidth"].values
        atr_vals = df["atr"].values
        close = df["close"].values

        for i in range(min_bars, n):
            if pd.isna(mid[i]) or pd.isna(bandwidth[i]) or pd.isna(atr_vals[i]):
                continue

            # 中轨斜率（用5日变化率近似角度）
            if pd.notna(mid[i - 5]) and mid[i - 5] > 0:
                slope = (mid[i] - mid[i - 5]) / mid[i - 5]
            else:
                slope = 0

            # 带宽是否处于历史最低 percentile
            bw_slice = bandwidth[i - self.SQUEEZE_LOOKBACK:i]
            bw_valid = bw_slice[~np.isnan(bw_slice)]
            if len(bw_valid) < 60:
                continue
            bw_percentile = (bw_valid < bandwidth[i]).sum() / len(bw_valid)

            # ATR 趋势（5日变化）
            if pd.notna(atr_vals[i - 5]) and atr_vals[i - 5] > 0:
                atr_change = atr_vals[i] / atr_vals[i - 5]
            else:
                atr_change = 1.0

            # 带宽趋势（5日变化）
            if pd.notna(bandwidth[i - 5]) and bandwidth[i - 5] > 0:
                bw_change = bandwidth[i] / bandwidth[i - 5]
            else:
                bw_change = 1.0

            is_mid_flat = abs(slope) < self.BB_SLOPE_THRESHOLD
            is_atr_stable = 0.85 < atr_change < 1.15
            is_atr_rising = atr_change > self.ATR_EXPAND_THRESHOLD
            is_atr_declining = atr_change < 0.85
            is_bw_expanding = bw_change > 1.1
            is_bw_narrow = bw_percentile < self.SQUEEZE_PERCENTILE

            if is_bw_narrow and is_atr_declining and is_mid_flat:
                env = "squeeze"
                env_label = "蓄势突破"
            elif abs(slope) > 0.01 and is_bw_expanding and is_atr_rising:
                env = "trend"
                if slope > 0:
                    env_label = "上升趋势"
                else:
                    env_label = "下降趋势"
            elif is_mid_flat:
                env = "range"
                env_label = "震荡格局"
            else:
                # 弱趋势/过渡态，按震荡处理
                env = "range"
                env_label = "震荡偏弱"

            df.loc[df.index[i], "environment"] = env
            df.loc[df.index[i], "env_label"] = env_label

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 3: KDJ 信号检测
    # ═══════════════════════════════════════════════════════════════

    def _detect_kdj_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测 KDJ 金叉/死叉、J 值极端、KDJ 背离"""
        n = len(df)
        df["kdj_golden_cross"] = 0
        df["kdj_death_cross"] = 0
        df["kdj_j_extreme_high"] = 0
        df["kdj_j_extreme_low"] = 0
        df["kdj_bottom_divergence"] = 0
        df["kdj_top_divergence"] = 0

        if n < max(self.DIV_LOOKBACK, 10):
            return df

        k_vals = df["kdj_k"].values
        d_vals = df["kdj_d"].values
        j_vals = df["kdj_j"].values
        close = df["close"].values

        for i in range(1, n):
            if pd.isna(k_vals[i]) or pd.isna(d_vals[i]) or pd.isna(j_vals[i]):
                continue

            # KDJ 金叉：K 上穿 D
            if k_vals[i] > d_vals[i] and k_vals[i - 1] <= d_vals[i - 1]:
                df.loc[df.index[i], "kdj_golden_cross"] = 1

            # KDJ 死叉：K 下穿 D
            if k_vals[i] < d_vals[i] and k_vals[i - 1] >= d_vals[i - 1]:
                df.loc[df.index[i], "kdj_death_cross"] = 1

            # J 值极端
            if j_vals[i] >= self.KDJ_OVERBOUGHT_J:
                df.loc[df.index[i], "kdj_j_extreme_high"] = 1
            if j_vals[i] <= self.KDJ_OVERSOLD_J:
                df.loc[df.index[i], "kdj_j_extreme_low"] = 1

        # KDJ 背离检测
        if n < self.DIV_LOOKBACK:
            return df

        for i in range(self.DIV_LOOKBACK, n):
            if pd.isna(close[i]) or pd.isna(j_vals[i]):
                continue

            prev_slice_close = close[i - self.DIV_LOOKBACK:i]
            prev_slice_d = d_vals[i - self.DIV_LOOKBACK:i]  # 用 D 值检测背离更稳定
            valid = ~np.isnan(prev_slice_close) & ~np.isnan(prev_slice_d)
            if valid.sum() < 20:
                continue

            # 底背离：价格新低 + D 值未新低
            close_min = np.min(prev_slice_close[valid])
            d_min = np.min(prev_slice_d[valid])
            if close[i] < close_min * 0.98 and d_vals[i] > d_min and d_vals[i] < 30:
                df.loc[df.index[i], "kdj_bottom_divergence"] = 1

            # 顶背离：价格新高 + D 值未新高
            close_max = np.max(prev_slice_close[valid])
            d_max = np.max(prev_slice_d[valid])
            if close[i] > close_max * 1.02 and d_vals[i] < d_max and d_vals[i] > 70:
                df.loc[df.index[i], "kdj_top_divergence"] = 1

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 4: 布林带信号检测
    # ═══════════════════════════════════════════════════════════════

    def _detect_bollinger_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测触轨、穿刺回归、沿轨爬行、Squeeze"""
        n = len(df)
        df["bb_touch_upper"] = 0
        df["bb_touch_lower"] = 0
        df["bb_pierce_upper_return"] = 0
        df["bb_pierce_lower_return"] = 0
        df["bb_walking_upper"] = 0
        df["bb_walking_lower"] = 0
        df["bb_squeeze"] = 0

        if n < 10:
            return df

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        boll_up = df["boll_up"].values
        boll_down = df["boll_down"].values
        mid = df["ma_mid"].values

        for i in range(3, n):
            if pd.isna(close[i]) or pd.isna(boll_up[i]) or pd.isna(boll_down[i]):
                continue

            # 触上轨
            if high[i] >= boll_up[i] and close[i] <= boll_up[i]:
                df.loc[df.index[i], "bb_touch_upper"] = 1

            # 触下轨
            if low[i] <= boll_down[i] and close[i] >= boll_down[i]:
                df.loc[df.index[i], "bb_touch_lower"] = 1

            # 穿刺上轨后回归
            if i >= 1 and close[i - 1] > boll_up[i - 1] and close[i] < boll_up[i]:
                df.loc[df.index[i], "bb_pierce_upper_return"] = 1

            # 穿刺下轨后回归
            if i >= 1 and close[i - 1] < boll_down[i - 1] and close[i] > boll_down[i]:
                df.loc[df.index[i], "bb_pierce_lower_return"] = 1

            # 沿上轨爬行（连续3根在布林上轨附近，中轨向上）
            if i >= 3 and pd.notna(mid[i]) and pd.notna(mid[i - 3]):
                near_upper = all(
                    close[i - j] > boll_up[i - j] * 0.98
                    for j in range(3)
                    if pd.notna(close[i - j]) and pd.notna(boll_up[i - j])
                )
                mid_up = mid[i] > mid[i - 3]
                if near_upper and mid_up:
                    df.loc[df.index[i], "bb_walking_upper"] = 1

            # 沿下轨爬行
            if i >= 3 and pd.notna(mid[i]) and pd.notna(mid[i - 3]):
                near_lower = all(
                    close[i - j] < boll_down[i - j] * 1.02
                    for j in range(3)
                    if pd.notna(close[i - j]) and pd.notna(boll_down[i - j])
                )
                mid_down = mid[i] < mid[i - 3]
                if near_lower and mid_down:
                    df.loc[df.index[i], "bb_walking_lower"] = 1

            # Squeeze（从环境判定中继承）
            if df["environment"].iloc[i] == "squeeze":
                df.loc[df.index[i], "bb_squeeze"] = 1

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 5: 周线布林带方向确认
    # ═══════════════════════════════════════════════════════════════

    def _calc_weekly_confirm(self, df: pd.DataFrame) -> pd.DataFrame:
        """周线布林带中轨方向过滤：朝上只做多，朝下只做空"""
        n = len(df)
        df["weekly_bb_bullish"] = 0
        df["weekly_bb_bearish"] = 0

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

            if len(weekly_close) < 22:
                return df

            # 计算周线布林带中轨
            weekly_mid = weekly_close.rolling(window=self.BB_N).mean()

            # 周线中轨方向判定（对比两周前）
            bullish_dates = []
            bearish_dates = []
            for j in range(self.BB_N + 2, len(weekly_mid)):
                if pd.notna(weekly_mid.iloc[j]) and pd.notna(weekly_mid.iloc[j - 2]):
                    if weekly_mid.iloc[j] > weekly_mid.iloc[j - 2]:
                        bullish_dates.append(weekly_mid.index[j])
                    elif weekly_mid.iloc[j] < weekly_mid.iloc[j - 2]:
                        bearish_dates.append(weekly_mid.index[j])

            # 映射回日线
            for i in range(n):
                try:
                    d = pd.Timestamp(df["date"].iloc[i])
                    fri = d + pd.offsets.Week(weekday=4, weekday_offset=0)
                    if d > fri:
                        fri = d + pd.offsets.Week(weekday=4)
                    for wd in bullish_dates:
                        if abs((fri - wd).days) <= 3:
                            df.loc[df.index[i], "weekly_bb_bullish"] = 1
                            break
                    for wd in bearish_dates:
                        if abs((fri - wd).days) <= 3:
                            df.loc[df.index[i], "weekly_bb_bearish"] = 1
                            break
                except Exception:
                    pass
        except Exception:
            pass

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 6: 信号分级 (C/B/A/S)
    # ═══════════════════════════════════════════════════════════════

    def _classify_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """四级信号分级 — 环境感知"""
        n = len(df)

        df["signal_grade"] = "NONE"
        df["signal_grade_label"] = ""
        df["buy_signal"] = 0
        df["sell_signal"] = 0
        df["is_enhanced"] = False

        min_bars = max(self.MA50_WINDOW + 10, self.SQUEEZE_LOOKBACK)
        for i in range(min_bars, n):
            env = df["environment"].iloc[i]
            if env == "unknown":
                continue

            close_val = df["close"].iloc[i]
            vol_ratio = df["volume_ratio"].iloc[i]
            atr_val = df["atr"].iloc[i]
            atr_prev = df["atr"].iloc[i - 5] if i >= 5 and pd.notna(df["atr"].iloc[i - 5]) else atr_val

            kdj_k = df["kdj_k"].iloc[i]
            kdj_d = df["kdj_d"].iloc[i]
            kdj_j = df["kdj_j"].iloc[i]
            kdj_j_prev = df["kdj_j"].iloc[i - 1] if i >= 1 else kdj_j

            golden_cross = df["kdj_golden_cross"].iloc[i] == 1
            death_cross = df["kdj_death_cross"].iloc[i] == 1
            j_extreme_high = df["kdj_j_extreme_high"].iloc[i] == 1
            j_extreme_low = df["kdj_j_extreme_low"].iloc[i] == 1
            j_turning_down = j_extreme_high and kdj_j < kdj_j_prev
            j_turning_up = j_extreme_low and kdj_j > kdj_j_prev

            touch_upper = df["bb_touch_upper"].iloc[i] == 1
            touch_lower = df["bb_touch_lower"].iloc[i] == 1
            pierce_upper_ret = df["bb_pierce_upper_return"].iloc[i] == 1
            pierce_lower_ret = df["bb_pierce_lower_return"].iloc[i] == 1
            walking_upper = df["bb_walking_upper"].iloc[i] == 1
            walking_lower = df["bb_walking_lower"].iloc[i] == 1
            is_squeeze = df["bb_squeeze"].iloc[i] == 1

            kdj_bottom_div = df["kdj_bottom_divergence"].iloc[i] == 1
            kdj_top_div = df["kdj_top_divergence"].iloc[i] == 1

            weekly_bull = df["weekly_bb_bullish"].iloc[i] == 1
            weekly_bear = df["weekly_bb_bearish"].iloc[i] == 1

            if pd.isna(close_val) or pd.isna(vol_ratio) or pd.isna(kdj_k):
                continue

            # ATR 状态
            atr_stable = pd.notna(atr_val) and pd.notna(atr_prev) and atr_prev > 0 and 0.85 < atr_val / atr_prev < 1.15
            atr_expanding = pd.notna(atr_val) and pd.notna(atr_prev) and atr_prev > 0 and atr_val / atr_prev >= self.ATR_EXPAND_THRESHOLD

            # 中轨斜率（5日内）
            mid = df["ma_mid"].values
            mid_flat = False
            if i >= 5 and pd.notna(mid[i]) and pd.notna(mid[i - 5]) and mid[i - 5] > 0:
                mid_flat = abs(mid[i] - mid[i - 5]) / mid[i - 5] < self.BB_SLOPE_THRESHOLD

            # ── 做多信号 ──
            has_long_basis = touch_lower or pierce_lower_ret
            has_kdj_long = golden_cross or j_turning_up or (pd.notna(kdj_j) and kdj_j < self.KDJ_OVERSOLD_J)

            if has_long_basis or has_kdj_long:
                grade = None

                # C 级：单指标
                if has_long_basis != has_kdj_long:  # 仅一个
                    grade = "C"

                # B 级：双指标确认
                if has_long_basis and has_kdj_long:
                    grade = "B"

                    # A 级：B + ATR稳定 + 中轨走平（震荡环境）
                    if atr_stable and mid_flat and env in ("range", "squeeze"):
                        grade = "A"

                # S 级：全系统共振
                squeeze_breakout_long = (
                    is_squeeze and
                    (pierce_lower_ret or (touch_lower and vol_ratio >= self.VOL_S_THRESHOLD)) and
                    atr_expanding
                )
                if kdj_bottom_div and (squeeze_breakout_long or (grade == "A" and vol_ratio >= self.VOL_S_THRESHOLD)):
                    grade = "S"

                # 周线方向过滤：周线看跌 → 做多降级
                if weekly_bear and grade in ("A", "B"):
                    grade = grade + "_weekly_against"
                elif weekly_bear and grade == "S":
                    grade = "A"  # S 降为 A

                if grade:
                    df.loc[df.index[i], "buy_signal"] = 1
                    df.loc[df.index[i], "signal_grade"] = grade
                    df.loc[df.index[i], "signal_grade_label"] = _grade_label(grade)
                    base_grade = grade.split("_")[0]
                    df.loc[df.index[i], "is_enhanced"] = base_grade in ("S", "A")

            # ── 做空信号 ──
            has_short_basis = touch_upper or pierce_upper_ret
            has_kdj_short = death_cross or j_turning_down or (pd.notna(kdj_j) and kdj_j > self.KDJ_OVERBOUGHT_J)

            if has_short_basis or has_kdj_short:
                # 趋势环境下的沿轨爬行 ≠ 做空信号
                if walking_upper and env == "trend":
                    continue

                grade = None

                if has_short_basis != has_kdj_short:
                    grade = "C"

                if has_short_basis and has_kdj_short:
                    grade = "B"

                    if atr_stable and mid_flat and env in ("range", "squeeze"):
                        grade = "A"

                squeeze_breakout_short = (
                    is_squeeze and
                    (pierce_upper_ret or (touch_upper and vol_ratio >= self.VOL_S_THRESHOLD)) and
                    atr_expanding
                )
                if kdj_top_div and (squeeze_breakout_short or (grade == "A" and vol_ratio >= self.VOL_S_THRESHOLD)):
                    grade = "S"

                # 周线方向过滤
                if weekly_bull and grade in ("A", "B"):
                    grade = grade + "_weekly_against"
                elif weekly_bull and grade == "S":
                    grade = "A"

                if grade:
                    df.loc[df.index[i], "sell_signal"] = 1
                    df.loc[df.index[i], "signal_grade"] = grade
                    df.loc[df.index[i], "signal_grade_label"] = _grade_label(grade)
                    base_grade = grade.split("_")[0]
                    df.loc[df.index[i], "is_enhanced"] = base_grade in ("S", "A")

        return df

    # ═══════════════════════════════════════════════════════════════
    # Phase 7: 出场条件
    # ═══════════════════════════════════════════════════════════════

    def _detect_exit_triggers(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测出场条件"""
        n = len(df)

        for col in [f"exit_trigger_{i}" for i in range(1, 6)]:
            df[col] = 0

        for i in range(5, n):
            close_val = df["close"].iloc[i]
            mid_val = df["ma_mid"].iloc[i]
            atr_val = df["atr"].iloc[i]
            atr_prev = df["atr"].iloc[i - 1] if i >= 1 else atr_val
            kdj_k = df["kdj_k"].iloc[i]
            kdj_k_prev = df["kdj_k"].iloc[i - 1] if i >= 1 else kdj_k
            kdj_d = df["kdj_d"].iloc[i]
            kdj_d_prev = df["kdj_d"].iloc[i - 1] if i >= 1 else kdj_d

            if pd.isna(close_val):
                continue

            # 1. 价格回归中轨（震荡/区间交易出场）
            if pd.notna(mid_val):
                boll_up = df["boll_up"].iloc[i]
                boll_down = df["boll_down"].iloc[i]
                if pd.notna(boll_up) and pd.notna(boll_down):
                    prev_close = df["close"].iloc[i - 1] if i >= 1 else close_val
                    # 从接近上轨回落到中轨下方
                    if prev_close > boll_up * 0.97 and close_val < mid_val:
                        df.loc[df.index[i], "exit_trigger_1"] = 1

            # 2. KDJ 死叉（做多出场）/ KDJ 金叉（做空出场）
            if pd.notna(kdj_k) and pd.notna(kdj_d) and pd.notna(kdj_d_prev):
                if kdj_k < kdj_d and kdj_k_prev >= kdj_d_prev:
                    df.loc[df.index[i], "exit_trigger_2"] = 1

            # 3. J 值从超买回落
            kdj_j = df["kdj_j"].iloc[i]
            kdj_j_prev = df["kdj_j"].iloc[i - 1] if i >= 1 else kdj_j
            if pd.notna(kdj_j) and pd.notna(kdj_j_prev):
                if kdj_j_prev > self.KDJ_OVERBOUGHT_J and kdj_j < 100:
                    df.loc[df.index[i], "exit_trigger_3"] = 1

            # 4. ATR 异常跳升（波动率突变 = 变盘预警）
            if pd.notna(atr_val) and pd.notna(atr_prev) and atr_prev > 0:
                if atr_val / atr_prev > 1.5:
                    df.loc[df.index[i], "exit_trigger_4"] = 1

            # 5. 价格跌破 MA20（做多辅助出场）
            ma20 = df["ma20"].iloc[i]
            if pd.notna(ma20) and ma20 > 0 and close_val < ma20:
                df.loc[df.index[i], "exit_trigger_5"] = 1

        return df

    # ═══════════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════════

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = self._ensure_indicators(df)
        df = self._detect_environment(df)
        df = self._detect_kdj_signals(df)
        df = self._detect_bollinger_signals(df)
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

        # 安全取值
        def _f(val, default=None):
            try:
                v = float(val)
                return round(v, 4) if pd.notna(v) and not np.isinf(v) else default
            except (ValueError, TypeError):
                return default

        close_val = _f(row.get("close"), 0)
        vol_ratio = _f(row.get("volume_ratio"))
        atr_val = _f(row.get("atr"))
        kdj_k = _f(row.get("kdj_k"))
        kdj_d = _f(row.get("kdj_d"))
        kdj_j = _f(row.get("kdj_j"))
        boll_up = _f(row.get("boll_up"))
        boll_mid = _f(row.get("ma_mid"))
        boll_down = _f(row.get("boll_down"))
        bandwidth = _f(row.get("bandwidth"))
        env = str(row.get("environment", "unknown"))
        env_label = str(row.get("env_label", "未知"))

        # 入场条件
        entry_conditions = {
            "environment": env,
            "environment_label": env_label,
            "kdj_golden_cross": bool(row.get("kdj_golden_cross")),
            "kdj_death_cross": bool(row.get("kdj_death_cross")),
            "kdj_j_extreme": bool(row.get("kdj_j_extreme_high") or row.get("kdj_j_extreme_low")),
            "bb_touch": bool(row.get("bb_touch_upper") or row.get("bb_touch_lower")),
            "bb_pierce_return": bool(row.get("bb_pierce_upper_return") or row.get("bb_pierce_lower_return")),
            "bb_squeeze": bool(row.get("bb_squeeze")),
            "volume_ok": vol_ratio is not None and vol_ratio >= self.VOL_A_THRESHOLD,
            "kdj_divergence": bool(row.get("kdj_bottom_divergence") or row.get("kdj_top_divergence")),
            "atr_confirm": True,  # 已通过分级逻辑保证
            "weekly_confirm": bool(row.get("weekly_bb_bullish") or row.get("weekly_bb_bearish")),
        }

        # 出场条件
        exit_triggers = []
        exit_labels = {
            "exit_trigger_1": "价格回归中轨",
            "exit_trigger_2": "KDJ交叉反转",
            "exit_trigger_3": "J值从超买区回落",
            "exit_trigger_4": "ATR异常跳升(变盘预警)",
            "exit_trigger_5": "价格跌破MA20",
        }
        for col, label in exit_labels.items():
            if row.get(col, 0) == 1:
                exit_triggers.append(label)

        # ATR 动态止损
        atr_stop_distance = None
        atr_stop_price = None
        if atr_val is not None and close_val is not None:
            multiplier = self.ATR_EXPAND_THRESHOLD if env == "trend" else 1.5
            atr_stop_distance = round(multiplier * atr_val, 2)
            if signal_type == "BUY":
                atr_stop_price = round(close_val - atr_stop_distance, 2)
            else:
                atr_stop_price = round(close_val + atr_stop_distance, 2)

        # 仓位建议
        grade_hints = {
            "S": "重仓交易（风险2-2.5%），ATR动态止损",
            "A": "标准仓位（风险1.5%），止损在反向轨道或1.5×ATR",
            "B": "轻仓试探（风险0.5-1%），止损严格",
            "C": "仅观察，不交易",
        }
        position_advice = grade_hints.get(base_grade, "")

        grade_labels = {"S": "S级-全系统共振", "A": "A级-标准入场", "B": "B级-试探", "C": "C级-仅观察"}
        grade_label = grade_labels.get(base_grade, grade)

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
                "signal_grade": base_grade,
                "signal_grade_full": grade,
                "signal_grade_label": grade_label,
                "environment": env,
                "environment_label": env_label,
                "kdj_k": round(kdj_k, 2) if kdj_k is not None else None,
                "kdj_d": round(kdj_d, 2) if kdj_d is not None else None,
                "kdj_j": round(kdj_j, 2) if kdj_j is not None else None,
                "atr": round(atr_val, 2) if atr_val is not None else None,
                "atr_stop_distance": atr_stop_distance,
                "atr_stop_price": atr_stop_price,
                "boll_up": round(boll_up, 2) if boll_up is not None else None,
                "boll_mid": round(boll_mid, 2) if boll_mid is not None else None,
                "boll_down": round(boll_down, 2) if boll_down is not None else None,
                "bandwidth": round(bandwidth, 2) if bandwidth is not None else None,
                "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
                "weekly_bb_bullish": bool(row.get("weekly_bb_bullish")),
                "weekly_bb_bearish": bool(row.get("weekly_bb_bearish")),
                "entry_conditions": entry_conditions,
                "exit_triggers": exit_triggers,
                "position_advice": position_advice,
                "display_fields": [
                    {"key": "price", "label": "价格", "format": "price"},
                    {"key": "signal_grade_label", "label": "信号等级", "format": "text"},
                    {"key": "environment_label", "label": "市场环境", "format": "text"},
                    {"key": "kdj_j", "label": "KDJ-J", "format": "text"},
                    {"key": "atr", "label": "ATR", "format": "text"},
                    {"key": "volume_ratio", "label": "量比", "format": "ratio"},
                ],
            },
        )


def _grade_label(grade: str) -> str:
    """信号等级代码 → 中文标签"""
    if grade.startswith("S"):
        return "S级-全系统共振"
    if grade.startswith("A"):
        return "A级-标准入场"
    if grade.startswith("B"):
        return "B级-试探"
    if grade.startswith("C"):
        return "C级-仅观察"
    return grade
