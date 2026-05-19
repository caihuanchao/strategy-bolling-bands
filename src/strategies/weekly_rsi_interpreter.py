"""
周线 RSI 策略结构化解读模块。

基于周线 RSI 策略深度指南，为个股生成 RSI 状态、背离检测、
中轴位置、信号摘要、操作建议五个维度的中文解读。
"""

import pandas as pd
import numpy as np


def interpret_weekly_rsi_all(df: pd.DataFrame) -> dict:
    """
    为周线 RSI 策略生成完整结构化解读。

    Args:
        df: DataFrame，需包含 weekly_rsi, buy_signal, sell_signal 列

    Returns:
        {"rsi_status": {...}, "divergence": {...}, "midline": {...},
         "signal_summary": {...}, "recommendation": {...}}
    """
    if "weekly_rsi" not in df.columns:
        return {"error": "数据不足：缺少 weekly_rsi 列"}

    rsi_vals = df["weekly_rsi"].dropna()
    if len(rsi_vals) < 2:
        return {"error": "数据不足：周线 RSI 数据点不足"}

    rsi_status = _interpret_rsi_status(rsi_vals)
    divergence = _interpret_divergence(df)
    midline = _interpret_midline(rsi_vals)
    signal_summary = _signal_summary(df, rsi_status, divergence, midline)
    recommendation = _recommendation(rsi_status, divergence, midline)

    return {
        "rsi_status": rsi_status,
        "divergence": divergence,
        "midline": midline,
        "signal_summary": signal_summary,
        "recommendation": recommendation,
    }


def _interpret_rsi_status(rsi_vals: pd.Series) -> dict:
    """判定周线 RSI 当前区间和趋势"""
    cur = float(rsi_vals.iloc[-1])
    prev = float(rsi_vals.iloc[-2]) if len(rsi_vals) >= 2 else cur

    # 区间判定（周线调整阈值）
    if cur <= 35:
        zone = "超卖区"
        zone_desc = "周线 RSI ≤ 35，处于中期超卖区域，通常对应阶段性底部"
    elif cur >= 65:
        zone = "超买区"
        zone_desc = "周线 RSI ≥ 65，处于中期超买区域，注意回调风险"
    elif cur < 50:
        zone = "偏弱区"
        zone_desc = "周线 RSI 在 35-50 之间，中期动能偏弱"
    else:
        zone = "偏强区"
        zone_desc = "周线 RSI 在 50-65 之间，中期动能偏强"

    # 趋势方向
    trend = "上升" if cur > prev else "下降" if cur < prev else "持平"
    cur_round = round(cur, 2)
    prev_round = round(prev, 2)

    return {
        "value": cur_round,
        "previous": prev_round,
        "zone": zone,
        "trend": trend,
        "summary": f"周线 RSI = {cur_round}，处于{zone}，{trend}趋势",
        "detail": f"{zone_desc}。近两周 RSI 从 {prev_round} 变为 {cur_round}。",
        "checklist": [
            "✓ 周线 RSI 处于超卖区可关注中期底部机会" if cur <= 35 else
            "✓ 周线 RSI 处于超买区需警惕中期回调" if cur >= 65 else
            "○ 周线 RSI 处于中性区间，趋势不明朗",
        ],
    }


def _interpret_divergence(df: pd.DataFrame) -> dict:
    """检测最近是否有背离信号（通过最近 10 根日线查询 buy_signal）"""
    recent_n = min(20, len(df))
    recent = df.iloc[-recent_n:]

    has_buy = int(recent["buy_signal"].sum()) > 0
    has_sell = int(recent["sell_signal"].sum()) > 0

    buy_dates = recent[recent["buy_signal"] == 1]
    sell_dates = recent[recent["sell_signal"] == 1]

    if has_buy and has_sell:
        status = "双向信号"
        summary = "近期同时出现买卖信号，市场分歧较大"
        detail = "周线级别出现双向信号通常出现在趋势转折期"
    elif has_buy:
        last_date = buy_dates["date"].iloc[-1] if "date" in buy_dates.columns else "最近"
        rsi_val = buy_dates["weekly_rsi"].iloc[-1] if "weekly_rsi" in buy_dates.columns else "N/A"
        status = "买入信号"
        summary = f"近期出现周线RSI底背离买入信号 ({last_date})"
        detail = f"RSI 从超卖区反弹伴随底背离，信号出现时周线 RSI ≈ {rsi_val}。" \
                 if rsi_val != "N/A" else "RSI 从超卖区反弹伴随底背离。"
    elif has_sell:
        last_date = sell_dates["date"].iloc[-1] if "date" in sell_dates.columns else "最近"
        status = "卖出信号"
        summary = f"近期出现周线RSI卖出信号 ({last_date})"
        detail = "卖出条件可能为：超买回落 / 顶背离 / 跌破50中轴。"
    else:
        status = "无信号"
        summary = "近期无周线RSI交易信号"
        detail = "周线信号频率低（一年2-3次），当前处于持仓或等待期。"

    return {
        "status": status,
        "summary": summary,
        "detail": detail,
    }


def _interpret_midline(rsi_vals: pd.Series) -> dict:
    """判定 RSI 中轴（50）位置"""
    cur = float(rsi_vals.iloc[-1])

    if cur >= 50:
        # 检查是否持续在 50 以上
        above_count = sum(1 for v in rsi_vals[-4:] if float(v) >= 50)
        if above_count >= 3:
            position = "持续上方"
            summary = "周线 RSI 持续在 50 中轴上方，中期牛市确认"
            detail = "回调至 50 附近可视为中期买入机会。"
        else:
            position = "上方"
            summary = "周线 RSI 在中轴上方，中期偏多"
            detail = "需观察是否能持续站稳 50 上方 2 周以上。"
    else:
        below_count = sum(1 for v in rsi_vals[-4:] if float(v) < 50)
        if below_count >= 3:
            position = "持续下方"
            summary = "周线 RSI 持续在 50 中轴下方，中期熊市格局"
            detail = "反弹至 50 附近可视为中期卖出或减仓机会。"
        else:
            position = "下方"
            summary = "周线 RSI 在中轴下方，中期偏空"
            detail = "关注是否能够从下方有效突破 50 中轴。"

    return {
        "position": position,
        "summary": summary,
        "detail": detail,
    }


def _signal_summary(df: pd.DataFrame, rsi_status: dict,
                    divergence: dict, midline: dict) -> dict:
    """生成综合信号摘要"""
    zone = rsi_status["zone"]
    trend = rsi_status["trend"]
    sig = divergence["status"]
    pos = midline["position"]

    if sig == "买入信号":
        overall = "偏多"
        desc = "周线RSI底背离买入信号已触发，中期看涨。"
    elif sig == "卖出信号":
        overall = "偏空"
        desc = "周线RSI卖出信号已触发，中期看跌。"
    elif zone == "超卖区" and trend == "上升":
        overall = "偏多"
        desc = "周线RSI处于超卖区且回升，等待底背离确认后可入场。"
    elif zone == "超买区" and trend == "下降":
        overall = "偏空"
        desc = "周线RSI从超买区回落，注意中期回调风险。"
    elif pos in ("持续上方",):
        overall = "偏多"
        desc = "中期牛市格局，回调是机会。"
    elif pos in ("持续下方",):
        overall = "偏空"
        desc = "中期熊市格局，反弹减仓。"
    else:
        overall = "中性"
        desc = "周线RSI无明确方向信号，以观望为主。"

    return {
        "overall": overall,
        "description": desc,
    }


def _recommendation(rsi_status: dict, divergence: dict, midline: dict) -> dict:
    """生成操作建议"""
    zone = rsi_status["zone"]
    sig = divergence["status"]
    pos = midline["position"]

    hints = []

    if sig == "买入信号":
        hints.append("周线RSI底背离买入信号已确认，可考虑分批建仓")
        hints.append("止损设置在背离低点下方 3-5%")
        hints.append("持仓周期预期 4-12 周，不宜短线操作")
    elif sig == "卖出信号":
        hints.append("周线RSI卖出信号触发，应考虑减仓或清仓")
        hints.append("若为顶背离卖出，可等待反弹再减仓")
    elif zone == "超卖区":
        hints.append("关注周线RSI是否出现底背离，不要急于抄底")
    elif zone == "超买区":
        hints.append("持有者可考虑逐步止盈，空仓者不宜追高")
    elif pos in ("持续上方",):
        hints.append("中期牛市，回调至50中轴附近可加仓")
    elif pos in ("持续下方",):
        hints.append("中期熊市，反弹至50中轴附近可减仓")
    else:
        hints.append("信号不明确，建议观望等待周线级别确认")

    hints.append("核心原则：周线定方向，日线定时机")

    return {
        "action": hints[0],
        "details": hints[1:],
    }
