"""
ETF 震荡波段策略结构化解读模块。

基于震荡走势 ETF 波段操作策略指南，为个股生成环境判定、RSI 状态、
布林带位置、K 线形态、失效预警、操作建议六个维度的中文解读。
"""

import pandas as pd
import numpy as np


def interpret_etf_oscillation_all(df: pd.DataFrame) -> dict:
    """
    为 ETF 震荡波段策略生成完整结构化解读。

    Args:
        df: DataFrame，需包含 environment, rsi, boll_up, boll_down, ma_mid,
            bandwidth, adx, ma20, ma60, pattern_* 列

    Returns:
        {"environment": {...}, "rsi_status": {...}, "bollinger_position": {...},
         "candlestick_pattern": {...}, "failure_warnings": {...}, "trading_advice": {...}}
    """
    required = ["environment", "rsi", "boll_up", "boll_down", "ma_mid"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"error": f"数据不足：缺少列 {missing}"}

    if len(df) < 20:
        return {"error": "数据不足：至少需要 20 条数据"}

    environment = _interpret_environment(df)
    rsi_status = _interpret_rsi(df)
    bollinger_position = _interpret_bollinger(df)
    candlestick_pattern = _interpret_candlestick(df)
    failure_warnings = _interpret_failure_warnings(df)
    trading_advice = _trading_advice(environment, rsi_status, bollinger_position,
                                      candlestick_pattern, failure_warnings, df)

    return {
        "environment": environment,
        "rsi_status": rsi_status,
        "bollinger_position": bollinger_position,
        "candlestick_pattern": candlestick_pattern,
        "failure_warnings": failure_warnings,
        "trading_advice": trading_advice,
    }


# ═══════════════════════════════════════════════════════════════
# 一、环境判定
# ═══════════════════════════════════════════════════════════════

def _interpret_environment(df: pd.DataFrame) -> dict:
    """判定当前市场环境"""
    if "environment" not in df.columns or "env_label" not in df.columns:
        return {"status": "unknown", "status_label": "未知", "summary": "环境数据不可用", "detail": "", "checklist": []}

    cur_env = str(df["environment"].iloc[-1]) if len(df) > 0 else "unknown"
    cur_label = str(df["env_label"].iloc[-1]) if len(df) > 0 else "未知"

    # 最近 20 天环境分布
    recent = df.iloc[-20:]
    env_counts = recent["environment"].value_counts() if "environment" in recent.columns else pd.Series()
    osc_days = int(env_counts.get("oscillation", 0))
    trans_days = int(env_counts.get("transition", 0))

    if cur_env == "oscillation":
        detail = "均线走平、ATR 稳定、箱体确认，当前适合震荡策略交易。"
        checklist = ["✓ 震荡环境确认，可执行波段操作", f"✓ 近 20 日震荡天数: {osc_days} 天"]
    elif cur_env == "transition":
        detail = "部分震荡条件不满足，市场处于过渡状态，震荡策略信号不可靠。"
        checklist = ["○ 过渡环境：震荡策略暂停，等待环境确认", f"○ 近 20 日过渡天数: {trans_days} 天"]
    else:
        detail = "均线斜率明显、ATR 扩张，趋势行情中震荡策略应暂停。"
        checklist = ["✗ 趋势环境：震荡策略不适用，应切换至趋势跟踪策略"]

    return {
        "status": cur_env,
        "status_label": cur_label,
        "summary": f"当前环境: {cur_label}",
        "detail": detail,
        "checklist": checklist,
    }


# ═══════════════════════════════════════════════════════════════
# 二、RSI 状态
# ═══════════════════════════════════════════════════════════════

def _interpret_rsi(df: pd.DataFrame) -> dict:
    """RSI 当前值和区间判定"""
    if "rsi" not in df.columns:
        return {"status": "unknown", "status_label": "未知", "summary": "RSI 数据不可用", "detail": "", "checklist": []}

    rsi_vals = df["rsi"].dropna()
    if len(rsi_vals) < 2:
        return {"status": "unknown", "status_label": "未知", "summary": "RSI 数据点不足", "detail": "", "checklist": []}

    cur = float(rsi_vals.iloc[-1])
    prev = float(rsi_vals.iloc[-2])

    if cur <= 35:
        zone, zone_desc = "超卖区", "RSI ≤ 35，处于超卖区，反弹概率较高"
        checklist = ["✓ RSI 超卖，配合布林带下轨可关注买入机会"]
    elif cur >= 65:
        zone, zone_desc = "超买区", "RSI ≥ 65，处于超买区，回调概率较高"
        checklist = ["✓ RSI 超买，配合布林带上轨可关注卖出机会"]
    elif cur < 50:
        zone, zone_desc = "偏弱区", "RSI 35-50，动能偏弱"
        checklist = ["○ RSI 偏弱但未超卖，继续等待"]
    else:
        zone, zone_desc = "偏强区", "RSI 50-65，动能偏强"
        checklist = ["○ RSI 偏强但未超买，继续等待"]

    trend = "上升" if cur > prev else "下降" if cur < prev else "持平"

    return {
        "value": round(cur, 2),
        "previous": round(prev, 2),
        "zone": zone,
        "trend": trend,
        "summary": f"RSI(14) = {round(cur, 1)}，处于{zone}，{trend}中",
        "detail": f"{zone_desc}。近两日 RSI 从 {round(prev, 1)} 变为 {round(cur, 1)}。",
        "checklist": checklist,
    }


# ═══════════════════════════════════════════════════════════════
# 三、布林带位置
# ═══════════════════════════════════════════════════════════════

def _interpret_bollinger(df: pd.DataFrame) -> dict:
    """判定收盘价在布林带中的位置"""
    if "close" not in df.columns or "boll_up" not in df.columns or "boll_down" not in df.columns:
        return {"status": "unknown", "status_label": "未知", "summary": "布林带数据不可用", "detail": "", "checklist": []}

    latest = df.iloc[-1]
    close_val = float(latest["close"])
    boll_up = float(latest["boll_up"])
    boll_mid = float(latest["ma_mid"])
    boll_down = float(latest["boll_down"])

    if pd.isna(close_val) or pd.isna(boll_up) or pd.isna(boll_mid) or pd.isna(boll_down):
        return {"status": "unknown", "status_label": "未知", "summary": "布林带数据不完整", "detail": "", "checklist": []}

    band_width = (boll_up - boll_down) / boll_mid * 100 if boll_mid > 0 else 0
    pos_in_band = (close_val - boll_down) / (boll_up - boll_down) * 100 if boll_up > boll_down else 50

    if close_val <= boll_down:
        position = "触及下轨"
        position_label = "超卖边界"
        checklist = ["✓ 价格触及下轨，震荡环境中是潜在的买入区域"]
    elif close_val >= boll_up:
        position = "触及上轨"
        position_label = "超买边界"
        checklist = ["✓ 价格触及上轨，震荡环境中是潜在的卖出区域"]
    elif pos_in_band < 30:
        position = "下半区"
        position_label = "偏弱"
        checklist = ["○ 价格在布林带下半区，接近下轨时可关注"]
    elif pos_in_band > 70:
        position = "上半区"
        position_label = "偏强"
        checklist = ["○ 价格在布林带上半区，接近上轨时可关注"]
    else:
        position = "中轨附近"
        position_label = "中性"
        checklist = ["○ 价格在中轨附近，暂无明确的边界交易机会"]

    return {
        "position": position,
        "position_label": position_label,
        "close": round(close_val, 3),
        "boll_up": round(boll_up, 3),
        "boll_mid": round(boll_mid, 3),
        "boll_down": round(boll_down, 3),
        "band_width_pct": round(band_width, 2),
        "pos_in_band_pct": round(pos_in_band, 1),
        "summary": f"收盘价 {close_val:.3f} 位于布林带{position}",
        "detail": f"上轨 {boll_up:.3f} / 中轨 {boll_mid:.3f} / 下轨 {boll_down:.3f}，带宽 {band_width:.1f}%",
        "checklist": checklist,
    }


# ═══════════════════════════════════════════════════════════════
# 四、K 线形态
# ═══════════════════════════════════════════════════════════════

def _interpret_candlestick(df: pd.DataFrame) -> dict:
    """检测最近 K 线形态"""
    pattern_cols = ["pattern_hammer", "pattern_shooting_star",
                    "pattern_bullish_engulfing", "pattern_bearish_engulfing"]
    has_patterns = all(c in df.columns for c in pattern_cols)

    if not has_patterns:
        return {"status": "no_data", "status_label": "无数据", "summary": "K 线形态数据不可用", "detail": "", "checklist": []}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    patterns_found = []
    if latest.get("pattern_hammer") == 1:
        patterns_found.append("锤子线（看涨反转）")
    if latest.get("pattern_shooting_star") == 1:
        patterns_found.append("射击之星（看跌反转）")
    if latest.get("pattern_bullish_engulfing") == 1:
        patterns_found.append("看涨吞没")
    if latest.get("pattern_bearish_engulfing") == 1:
        patterns_found.append("看跌吞没")

    if patterns_found:
        status = "形态确认"
        summary = f"最新 K 线出现: {' | '.join(patterns_found)}"
        detail = "K 线形态确认可以增强 BB+RSI 信号的可信度，将 B 级升级为 A 级。"
        checklist = [f"✓ 出现 {p}，增强对应方向信号的可靠性" for p in patterns_found]
    else:
        status = "无形态"
        summary = "最新 K 线无明确反转形态"
        detail = "缺少 K 线形态确认时，BB+RSI 信号仍可触发（B 级基础信号），但可信度相对较低。"
        checklist = ["○ 无 K 线形态增强，当前仅有基础信号（如有）"]

    return {
        "status": status,
        "status_label": "有形态" if patterns_found else "无形态",
        "patterns": patterns_found,
        "summary": summary,
        "detail": detail,
        "checklist": checklist,
    }


# ═══════════════════════════════════════════════════════════════
# 五、失效预警
# ═══════════════════════════════════════════════════════════════

def _interpret_failure_warnings(df: pd.DataFrame) -> dict:
    """检测震荡策略失效预警信号"""
    warnings = []
    n = len(df)

    if n < 20:
        return {"status": "ok", "status_label": "正常", "warnings": [], "summary": "数据不足，无法检测预警",
                "detail": "", "checklist": []}

    latest = df.iloc[-1]

    # 1. 带宽是否扩张
    if "bandwidth" in df.columns:
        bw_vals = df["bandwidth"].dropna()
        if len(bw_vals) >= 20:
            cur_bw = float(bw_vals.iloc[-1])
            bw_max_20 = float(bw_vals.iloc[-20:].max())
            if cur_bw >= bw_max_20 and bw_max_20 > 0:
                warnings.append("带宽20日最高，突破在即，暂停震荡策略")

    # 2. ADX 突破
    if "adx" in df.columns:
        adx_vals = df["adx"].dropna()
        if len(adx_vals) >= 6:
            cur_adx = float(adx_vals.iloc[-1])
            prev_adx = float(adx_vals.iloc[-6])
            if cur_adx > 25 and prev_adx < 20:
                warnings.append(f"ADX 从 {prev_adx:.1f} 升破 25（当前 {cur_adx:.1f}），趋势启动信号")

    # 3. MA 发散
    if "ma20" in df.columns and "ma60" in df.columns:
        ma20_vals = df["ma20"].dropna()
        ma60_vals = df["ma60"].dropna()
        if len(ma20_vals) >= 6 and len(ma60_vals) >= 6:
            if ma20_vals.iloc[-6] > 0 and ma60_vals.iloc[-6] > 0:
                slope_20 = (float(ma20_vals.iloc[-1]) - float(ma20_vals.iloc[-6])) / float(ma20_vals.iloc[-6])
                slope_60 = (float(ma60_vals.iloc[-1]) - float(ma60_vals.iloc[-6])) / float(ma60_vals.iloc[-6])
                if abs(slope_20 - slope_60) > 0.01:
                    warnings.append("均线从缠绕转为发散，趋势方向确立")

    if warnings:
        status = "warning"
        summary = f"触发 {len(warnings)} 个失效预警"
        detail = " | ".join(warnings)
        checklist = ["✗ " + w for w in warnings]
    else:
        status = "ok"
        summary = "无失效预警，震荡环境正常"
        detail = "布林带宽、ADX、均线结构均未发出趋势转换信号。"
        checklist = ["✓ 震荡策略可正常执行"]

    return {
        "status": status,
        "status_label": "预警中" if warnings else "正常",
        "warnings": warnings,
        "summary": summary,
        "detail": detail,
        "checklist": checklist,
    }


# ═══════════════════════════════════════════════════════════════
# 六、操作建议
# ═══════════════════════════════════════════════════════════════

def _trading_advice(environment: dict, rsi_status: dict, bollinger: dict,
                    candle: dict, warnings: dict, df: pd.DataFrame) -> dict:
    """综合所有维度生成操作建议"""
    hints = []

    # 检查信号
    recent = df.iloc[-5:]
    has_buy = int(recent["buy_signal"].sum()) > 0 if "buy_signal" in recent.columns else False
    has_sell = int(recent["sell_signal"].sum()) > 0 if "sell_signal" in recent.columns else False

    env = environment.get("status", "unknown")

    if warnings.get("status") == "warning":
        hints.append("⚠ 震荡策略失效预警已触发，建议立即减仓或清仓观望")
        hints.append("切换至趋势跟踪策略（周线 RSI 或三重确认），不要逆势操作")
    elif has_buy:
        grade = "A级" if df["signal_grade"].iloc[-1] == "A" else "B级"
        hints.append(f"✅ 买入信号已触发（{grade}），可考虑在震荡区间下沿建仓")
        hints.append("止损设置在布林带下轨下方 2%-3%")
        hints.append("目标止盈位在布林带中轨或上轨附近")
    elif has_sell:
        hints.append("✅ 卖出信号已触发，应考虑减仓或清仓")
        hints.append("若为失效预警触发的卖出，应全部离场等待趋势明朗")
    elif env == "oscillation" and rsi_status.get("zone") == "超卖区":
        hints.append("当前震荡环境中 RSI 超卖，密切关注布林带下轨的买入机会")
        hints.append("等待 BB 触下轨 + RSI 确认 + K 线形态后入场")
    elif env == "oscillation" and rsi_status.get("zone") == "超买区":
        hints.append("当前震荡环境中 RSI 超买，持有者考虑在布林带上轨减仓")
    elif env == "oscillation":
        hints.append("当前震荡格局正常，等待 BB 触轨 + RSI 极端值的入场机会")
    elif env in ("transition", "trend"):
        hints.append("⏸ 当前非震荡环境，震荡策略暂停执行")
        hints.append("切换到趋势类策略（布林带趋势模式或周线 RSI）")

    hints.append("核心原则：震荡策略吃均值回归，一旦区间破坏立即切换思维")

    return {
        "action": hints[0],
        "details": hints[1:],
    }
