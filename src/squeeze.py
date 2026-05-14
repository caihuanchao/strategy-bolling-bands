"""布林带收口突破检测模块"""

import math
import pandas as pd
import numpy as np


def detect_squeeze_breakout(
    df: pd.DataFrame,
    squeeze_threshold: float = 0.1,
    vol_window: int = 10,
    vol_ratio_threshold: float = 1.5,
) -> pd.DataFrame:
    """
    检测布林带收口和突破状态

    参数：
    - squeeze_threshold: 带宽/中轨 < 此值判定为收口，默认 0.1 (10%)
    - vol_window: 计算均量的窗口
    - vol_ratio_threshold: 突破所需成交量放大倍数

    要求输入 df 已包含: boll_up, boll_down, ma_mid, close, volume

    新增列：
    - band_width_pct: 带宽百分比
    - is_squeeze: 当前是否处于收口状态
    - breakout_up: 向上突破 (前一日收口 + 收盘价突破前一日上轨 + 放量)
    - breakout_down: 向下突破
    - breakout_direction: "up" / "down" / None
    """
    df = df.copy()

    # 计算带宽
    df["band_width_pct"] = (df["boll_up"] - df["boll_down"]) / df["ma_mid"]

    # 收口状态
    df["is_squeeze"] = (
        df["band_width_pct"].notna()
        & ~np.isinf(df["band_width_pct"])
        & (df["band_width_pct"] < squeeze_threshold)
    )

    # 成交量均线和放量条件
    df["_vol_ma"] = df["volume"].rolling(window=vol_window).mean()
    df["_vol_boost"] = df["volume"] > (df["_vol_ma"] * vol_ratio_threshold)

    # 突破检测：前一日收口 + 当日突破前一日轨道 + 放量
    prev_squeeze = df["is_squeeze"].shift(1)
    prev_upper = df["boll_up"].shift(1)
    prev_lower = df["boll_down"].shift(1)

    df["breakout_up"] = (
        prev_squeeze
        & (df["close"] > prev_upper)
        & df["_vol_boost"]
    )
    df["breakout_down"] = (
        prev_squeeze
        & (df["close"] < prev_lower)
        & df["_vol_boost"]
    )

    df["breakout_direction"] = np.where(
        df["breakout_up"],
        "up",
        np.where(df["breakout_down"], "down", None),
    )

    # 清理临时列
    df.drop(columns=["_vol_ma", "_vol_boost"], inplace=True)

    return df


def scan_squeeze_history(
    df: pd.DataFrame,
    max_events: int = 20,
    squeeze_threshold: float = 0.1,
) -> list:
    """
    扫描历史上所有收口→突破事件

    返回格式: [{date, direction, bandwidth_pct, volume_ratio}]

    连续突破合并规则: 间隔 ≤ 2 天视为同一事件，取其中 volume_ratio 最大的一天
    """
    df = detect_squeeze_breakout(df, squeeze_threshold=squeeze_threshold)

    # 筛选突破行
    event_rows = df[df["breakout_up"] | df["breakout_down"]].copy()
    if len(event_rows) == 0:
        return []

    # 构建 volume_ratio
    event_rows["_vol_ratio"] = event_rows["volume"] / event_rows["volume"].rolling(
        window=10
    ).mean().shift(0)
    # 用完整 df 算 vol_ma
    vol_ma_10 = df["volume"].rolling(window=10).mean()
    event_rows["_vol_ratio"] = event_rows["volume"] / vol_ma_10.loc[
        event_rows.index
    ].values
    event_rows["_vol_ratio"] = event_rows["_vol_ratio"].fillna(1.0)

    # 合并连续事件: gap ≤ 2 天归为同一事件
    indices = list(event_rows.index)
    groups = []
    current_group = [indices[0]]

    for i in range(1, len(indices)):
        gap = indices[i] - indices[i - 1]
        if gap <= 2:
            current_group.append(indices[i])
        else:
            groups.append(current_group)
            current_group = [indices[i]]
    groups.append(current_group)

    events = []
    for group in groups:
        # 取 volume_ratio 最大的一行作为代表
        group_df = event_rows.loc[group]
        best_idx = group_df["_vol_ratio"].idxmax()
        best = group_df.loc[best_idx]

        direction = "up" if best["breakout_up"] else "down"
        bw_pct = float(best["band_width_pct"])
        vol_ratio = float(best["_vol_ratio"])

        events.append(
            {
                "date": str(best.get("date", "")),
                "direction": direction,
                "bandwidth_pct": round(bw_pct, 4) if not (math.isnan(bw_pct) or math.isinf(bw_pct)) else 0,
                "volume_ratio": round(vol_ratio, 2) if not (math.isnan(vol_ratio) or math.isinf(vol_ratio)) else 0,
            }
        )

    # 按日期倒序，取最近事件
    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:max_events]


def check_cross_validation(breakout_direction: str, latest_row) -> str:
    """
    检查收口突破方向与现有布林带信号的交叉验证

    参数：
    - breakout_direction: "up" / "down" / None
    - latest_row: DataFrame 行 (Series 或 dict)，含 buy_signal / sell_signal

    返回: "confirmed" | "divergent" | "neutral"
    """
    if not breakout_direction or breakout_direction not in ("up", "down"):
        return "neutral"

    buy = int(latest_row.get("buy_signal", 0) or 0)
    sell = int(latest_row.get("sell_signal", 0) or 0)

    if breakout_direction == "up":
        if buy == 1:
            return "confirmed"
        if sell == 1:
            return "divergent"
    else:  # down
        if sell == 1:
            return "confirmed"
        if buy == 1:
            return "divergent"

    return "neutral"
