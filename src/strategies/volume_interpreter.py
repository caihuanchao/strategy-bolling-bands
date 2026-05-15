"""
成交量分析策略结构化解读模块。

基于成交量分析策略深度指南，为个股生成量价关系、背离、放量突破、
缩量回调、OBV、形态识别、操作建议七个维度的中文解读。
"""

import pandas as pd
import numpy as np


def interpret_volume_all(df: pd.DataFrame) -> dict:
    """
    为成交量分析策略生成完整结构化解读。

    Args:
        df: DataFrame，需包含 close, volume, volume_ratio, obv, divergence_top,
            divergence_bottom, breakout_buy, contraction_buy, pattern_score_sum,
            pattern_climax_buy, pattern_climax_sell, conditions_met, buy_signal, sell_signal 列

    Returns:
        {"price_volume_relation": {...}, "divergence": {...}, "breakout": {...},
         "pullback": {...}, "obv": {...}, "pattern": {...}, "trading_advice": {...}}
    """
    required = ["close", "volume", "volume_ratio", "obv"]
    if not all(c in df.columns for c in required):
        return {"error": "数据不足：缺少 close/volume/volume_ratio/obv 列"}

    latest = df.iloc[-1]
    if pd.isna(latest.get("close")) or pd.isna(latest.get("volume_ratio")):
        return {"error": "数据不足：最新数据缺失"}

    relation = _interpret_price_volume_relation(df)
    divergence = _interpret_divergence(df)
    breakout = _interpret_breakout(df)
    pullback = _interpret_pullback(df)
    obv_analysis = _interpret_obv(df)
    pattern = _interpret_pattern(df)
    trading_advice = _trading_advice(relation, divergence, breakout, pullback, obv_analysis, pattern, df)

    return {
        "price_volume_relation": relation,
        "divergence": divergence,
        "breakout": breakout,
        "pullback": pullback,
        "obv": obv_analysis,
        "pattern": pattern,
        "trading_advice": trading_advice,
    }


# ── 量价关系 ────────────────────────────────────────────────────────────────

def _interpret_price_volume_relation(df: pd.DataFrame) -> dict:
    """判断当前量价关系：价涨量增/价涨量缩/价跌量增/价跌量缩/价平量突增"""
    result = {}

    close_arr = df["close"].values
    vr_arr = df["volume_ratio"].values
    if len(close_arr) < 2:
        return {"status": "data_insufficient", "summary": "数据不足，无法判定量价关系"}

    price_change = float(close_arr[-1] - close_arr[-2])
    vol_ratio = float(vr_arr[-1])
    price_pct = price_change / float(close_arr[-2]) * 100 if close_arr[-2] != 0 else 0

    result["price_change_pct"] = round(price_pct, 2)
    result["volume_ratio"] = round(vol_ratio, 2)

    if abs(price_pct) < 0.3 and vol_ratio >= 2.0:
        result["status"] = "flat_surge"
        result["status_label"] = "价平量突增"
        result["detail"] = (
            f"价格微幅波动({price_pct:+.2f}%)但量比骤升至{vol_ratio:.1f}x："
            "这是变盘前兆。价格停滞但成交量突然放大，说明多空分歧加剧，"
            "方向即将选择。关注突破方向顺势操作。"
        )
    elif price_pct > 0 and vol_ratio >= 1.2:
        result["status"] = "up_with_volume"
        result["status_label"] = "价涨量增"
        result["detail"] = (
            f"价格上涨{price_pct:+.2f}%配合量比{vol_ratio:.1f}x："
            "上涨趋势健康，多头力量充足。大量资金认可当前价格并愿意追入，"
            "这是最健康的上涨模式。"
        )
    elif price_pct > 0 and vol_ratio < 1.0:
        result["status"] = "up_no_volume"
        result["status_label"] = "价涨量缩"
        result["detail"] = (
            f"价格上涨{price_pct:+.2f}%但量比仅{vol_ratio:.1f}x："
            "上涨动力衰竭，少数人推动价格而多数人不认可。"
            "警惕随时可能出现的反转，不宜追高。"
        )
    elif price_pct < 0 and vol_ratio >= 1.2:
        result["status"] = "down_with_volume"
        result["status_label"] = "价跌量增"
        result["detail"] = (
            f"价格下跌{price_pct:+.2f}%配合量比{vol_ratio:.1f}x："
            "抛压沉重，大量资金不计成本地出逃。"
            "下跌趋势强劲，不宜轻易抄底。"
        )
    elif price_pct < 0 and vol_ratio < 1.0:
        result["status"] = "down_no_volume"
        result["status_label"] = "价跌量缩"
        result["detail"] = (
            f"价格下跌{price_pct:+.2f}%但量比仅{vol_ratio:.1f}x："
            "卖盘枯竭，恐慌抛售减少。下跌可能接近尾声，"
            "等待放量阳线确认后可关注入场机会。"
        )
    else:
        result["status"] = "neutral"
        result["status_label"] = "量价平稳"
        result["detail"] = "价格变动不大，成交量正常，无明显量价信号。"

    result["summary"] = _relation_summary(result)
    result["checklist"] = _relation_checklist(result)
    return result


def _relation_summary(r: dict) -> str:
    mapping = {
        "flat_surge": "价平量突增是变盘前兆，密切关注突破方向。",
        "up_with_volume": "价涨量增，上涨趋势健康，顺势持有。",
        "up_no_volume": "价涨量缩，上涨动力衰竭，警惕反转。",
        "down_with_volume": "价跌量增，抛压沉重，不宜抄底。",
        "down_no_volume": "价跌量缩，卖盘枯竭，可能止跌企稳。",
    }
    return mapping.get(r.get("status", ""), "量价关系中性，无明确信号。")


def _relation_checklist(r: dict) -> list:
    status = r.get("status", "")
    items = []
    if status == "flat_surge":
        items.append("价平量突增：方向即将选择，不预判方向，等突破后顺势")
    elif status == "up_with_volume":
        items.append("价涨量增：趋势健康，可持有或加仓，沿均线移动止损")
    elif status == "up_no_volume":
        items.append("价涨量缩：动力衰减，考虑减仓或收紧止损")
    elif status == "down_with_volume":
        items.append("价跌量增：抛压重，不接飞刀，等待缩量止跌信号")
    elif status == "down_no_volume":
        items.append("价跌量缩：卖盘枯竭，关注是否为底部区域，等放量阳线确认")
    else:
        items.append("量价平稳：继续观望，等待明确信号")
    return items


# ── 背离分析 ────────────────────────────────────────────────────────────────

def _interpret_divergence(df: pd.DataFrame) -> dict:
    """量价背离分析"""
    result = {}

    has_top_col = "divergence_top" in df.columns
    has_bottom_col = "divergence_bottom" in df.columns

    if not has_top_col or not has_bottom_col:
        result["status"] = "data_insufficient"
        result["summary"] = "背离数据不可用"
        result["detail"] = "缺少 divergence_top/divergence_bottom 列，无法进行背离分析。"
        result["checklist"] = []
        return result

    # 检查近5日背离信号
    end = len(df)
    start = max(0, end - 5)
    recent = df.iloc[start:end]

    top_count = int(recent["divergence_top"].sum()) if "divergence_top" in recent.columns else 0
    bottom_count = int(recent["divergence_bottom"].sum()) if "divergence_bottom" in recent.columns else 0

    result["top_divergence_count"] = top_count
    result["bottom_divergence_count"] = bottom_count

    if top_count > 0:
        result["status"] = "top_divergence"
        result["status_label"] = "顶背离预警"
        result["detail"] = (
            "近5日检测到量价顶背离：价格创新高但成交量未能同步放大。"
            "上涨缺乏资金支持，这是上涨动能衰竭的信号。"
            "顶背离是可靠性较高的看跌信号（★★★★☆），应考虑减仓或设置更紧的止损。"
        )
    elif bottom_count > 0:
        result["status"] = "bottom_divergence"
        result["status_label"] = "底背离信号"
        result["detail"] = (
            "近5日检测到量价底背离：价格创新低但成交量未同步放大（恐慌盘减少）。"
            "下跌动能衰竭，卖盘力量减弱。底背离是可靠性较高的看涨信号（★★★★☆），"
            "等待放量阳线确认后可考虑入场。"
        )
    else:
        # 检查成交量趋势方向
        if len(df) >= 5:
            recent_vr = df["volume_ratio"].iloc[-5:].mean()
            older_vr = df["volume_ratio"].iloc[-10:-5].mean() if len(df) >= 10 else recent_vr
            if recent_vr > older_vr * 1.2:
                result["status"] = "volume_expanding"
                result["status_label"] = "量能扩张"
                result["detail"] = "成交量近期呈现扩张趋势，市场参与度提升，关注是否能形成有效突破。"
            elif recent_vr < older_vr * 0.8:
                result["status"] = "volume_contracting"
                result["status_label"] = "量能收敛"
                result["detail"] = "成交量近期呈现收敛趋势，市场参与度下降，可能进入盘整蓄力阶段。"
            else:
                result["status"] = "neutral"
                result["status_label"] = "无明显背离"
                result["detail"] = "近5日无明显量价背离信号，量价关系正常。"
        else:
            result["status"] = "neutral"
            result["status_label"] = "无明显背离"
            result["detail"] = "数据不足以进行背离分析。"

    result["summary"] = _divergence_summary(result)
    result["checklist"] = _divergence_checklist(result)
    return result


def _divergence_summary(r: dict) -> str:
    mapping = {
        "top_divergence": "顶背离预警：价格新高无量配合，上涨动能衰竭，注意减仓。",
        "bottom_divergence": "底背离信号：价格新低量能萎缩，下跌动能衰竭，等待放量确认。",
        "volume_expanding": "量能扩张中，市场活跃度上升，关注方向选择。",
        "volume_contracting": "量能收敛中，市场进入盘整，等待放量变盘。",
    }
    return mapping.get(r.get("status", ""), "背离信号不明显，量价关系正常。")


def _divergence_checklist(r: dict) -> list:
    status = r.get("status", "")
    items = []
    if status == "top_divergence":
        items.append("顶背离是减仓信号，不是加仓信号")
        items.append("确认条件：后续若放量阴线出现，应果断离场")
    elif status == "bottom_divergence":
        items.append("底背离是关注信号，不急于入场——等放量阳线二次确认")
        items.append("止损设在最近低点下方")
    elif status == "volume_contracting":
        items.append("量能收敛：降低交易频率，等待放量方向选择")
    elif status == "volume_expanding":
        items.append("量能扩张：关注是否能配合价格突破形成有效信号")
    else:
        items.append("无背离信号：按正常交易计划执行")
    return items


# ── 放量突破分析 ────────────────────────────────────────────────────────────

def _interpret_breakout(df: pd.DataFrame) -> dict:
    """放量突破分析"""
    result = {}

    has_breakout = "breakout_buy" in df.columns
    if not has_breakout:
        result["status"] = "data_insufficient"
        result["summary"] = "突破数据不可用"
        result["detail"] = ""
        result["checklist"] = []
        return result

    latest_vr = float(df["volume_ratio"].iloc[-1])
    latest_pc = float(df["close"].iloc[-1]) - float(df["close"].iloc[-2]) if len(df) >= 2 else 0
    is_breakout = int(df["breakout_buy"].iloc[-1]) == 1 if "breakout_buy" in df.columns else False

    result["volume_ratio"] = round(latest_vr, 2)
    result["is_breakout"] = is_breakout

    if latest_vr >= 3.0:
        result["level"] = "extreme"
        result["level_label"] = "天量"
        result["detail"] = (
            f"量比 {latest_vr:.1f}x（≥3.0）：天量级别。"
            + ("突破伴随天量，需警惕「天量天价」——可能是最大的买家已经进场，"
               "后续难有更大的买盘来继续推升。如果这是在连续大涨之后，"
               "更可能是出货而非突破。")
        )
    elif latest_vr >= 2.0:
        result["level"] = "strong"
        result["level_label"] = "显著放量"
        result["detail"] = (
            f"量比 {latest_vr:.1f}x（2.0-3.0）：显著放量。"
            + ("放量突破可信度较高，强烈做多信号。"
               if is_breakout else "成交量显著放大，关注是否能形成有效突破。")
        )
    elif latest_vr >= 1.5:
        result["level"] = "moderate"
        result["level_label"] = "温和放量"
        result["detail"] = (
            f"量比 {latest_vr:.1f}x（1.5-2.0）：温和放量。"
            + ("突破有一定可信度，但信号强度中等。"
               if is_breakout else "成交量温和放大，关注后续量能是否能持续。")
        )
    elif latest_vr >= 1.2:
        result["level"] = "mild"
        result["level_label"] = "轻微放量"
        result["detail"] = f"量比 {latest_vr:.1f}x（1.2-1.5）：轻微放量，突破信号偏弱。"
    else:
        result["level"] = "insufficient"
        result["level_label"] = "未放量"
        result["detail"] = f"量比 {latest_vr:.1f}x（<1.2）：成交量未有效放大，无突破信号。"

    result["summary"] = f"放量突破：{result['level_label']}（量比 {latest_vr:.1f}x）" + (
        "，突破信号有效。" if is_breakout else "，暂未形成有效突破。"
    )
    result["checklist"] = _breakout_checklist(result)
    return result


def _breakout_checklist(r: dict) -> list:
    items = []
    level = r.get("level", "")
    if level == "extreme":
        items.append("天量突破：警惕'天量天价'，连续大涨后的天量应以减仓为主")
    elif level in ("strong", "moderate"):
        items.append("放量突破：确认收盘站在突破位之外，可考虑顺势入场")
    elif r.get("is_breakout"):
        items.append("轻微突破：轻仓试探，等更强放量确认后加仓")
    else:
        items.append("无突破信号：继续等待放量突破确认")
    return items


# ── 缩量回调分析 ────────────────────────────────────────────────────────────

def _interpret_pullback(df: pd.DataFrame) -> dict:
    """缩量回调分析"""
    result = {}

    has_contraction = "contraction_buy" in df.columns
    has_ma20 = "ma20" in df.columns

    if not has_contraction:
        result["status"] = "data_insufficient"
        result["summary"] = "缩量回调数据不可用"
        result["detail"] = ""
        result["checklist"] = []
        return result

    is_contraction = int(df["contraction_buy"].iloc[-1]) == 1 if len(df) > 0 else False
    latest_vr = float(df["volume_ratio"].iloc[-1])
    is_uptrend = bool(df["is_uptrend"].iloc[-1]) if "is_uptrend" in df.columns else False

    result["volume_ratio"] = round(latest_vr, 2)
    result["is_uptrend"] = is_uptrend
    result["is_contraction_signal"] = is_contraction

    if is_contraction:
        result["status"] = "active"
        result["status_label"] = "缩量回调确认"
        result["detail"] = (
            f"上升趋势中价格回踩，量比仅{latest_vr:.1f}x（缩量至均量50%以下）："
            "这是洗盘而非反转。持有者惜售、卖盘稀疏，缩量回调至均线支撑处，"
            "是加仓良机。牛市中的缩量回调是市场给的机会。"
        )
    elif is_uptrend and latest_vr < 0.8:
        result["status"] = "approaching"
        result["status_label"] = "缩量但未止跌"
        result["detail"] = (
            f"上升趋势中成交量萎缩（量比{latest_vr:.1f}x），但价格仍在回落中。"
            "关注止跌企稳信号——当价格止跌+缩量同时出现时，是不错的入场时机。"
        )
    elif not is_uptrend and latest_vr > 1.2:
        result["status"] = "bearish_pullback"
        result["status_label"] = "放量下跌"
        result["detail"] = (
            f"当前不在上升趋势中（价格低于MA20），且量比{latest_vr:.1f}x显示放量下跌。"
            "这不是缩量回调机会——放量下跌意味着趋势可能转向。不宜做多。"
        )
    else:
        result["status"] = "none"
        result["status_label"] = "无缩量回调信号"
        result["detail"] = "当前不满足缩量回调条件（需要：上升趋势 + 价格回撤 + 缩量至50%以下 + 止跌）。"

    result["summary"] = _pullback_summary(result)
    result["checklist"] = _pullback_checklist(result)
    return result


def _pullback_summary(r: dict) -> str:
    mapping = {
        "active": "缩量回调确认：上升趋势中的健康回调，是加仓/入场时机。",
        "approaching": "缩量但未完全确认：等待止跌信号后入场更安全。",
        "bearish_pullback": "放量下跌：不符合缩量回调模式，不宜做多。",
    }
    return mapping.get(r.get("status", ""), "当前无明显缩量回调信号。")


def _pullback_checklist(r: dict) -> list:
    status = r.get("status", "")
    items = []
    if status == "active":
        items.append("缩量回调确认：可在均线支撑位附近入场")
        items.append("止损设在回调低点下方，保护下行风险")
    elif status == "approaching":
        items.append("等待止跌K线（十字星或小阳线）确认后再入场")
    elif status == "bearish_pullback":
        items.append("放量下跌不宜抄底，等缩量止跌信号出现")
    else:
        items.append("继续关注量价结构，等待缩量回调机会")
    return items


# ── OBV 分析 ─────────────────────────────────────────────────────────────────

def _interpret_obv(df: pd.DataFrame) -> dict:
    """OBV 能量潮分析"""
    result = {}

    if "obv" not in df.columns:
        return {"status": "data_insufficient", "summary": "OBV 数据不可用", "detail": "", "checklist": []}

    obv_arr = df["obv"].values
    close_arr = df["close"].values
    if len(obv_arr) < 10:
        result["status"] = "data_insufficient"
        result["summary"] = "OBV 数据不足（需要至少10个周期）"
        result["detail"] = ""
        result["checklist"] = []
        return result

    cur_obv = float(obv_arr[-1])
    obv_5_ago = float(obv_arr[-5]) if len(obv_arr) >= 5 else cur_obv
    obv_10_ago = float(obv_arr[-10])

    # OBV 趋势
    if cur_obv > obv_10_ago:
        obv_trend = "上升"
    elif cur_obv < obv_10_ago:
        obv_trend = "下降"
    else:
        obv_trend = "走平"

    result["obv_trend"] = obv_trend

    # OBV 与价格关系
    price_10_ago = float(close_arr[-10])
    cur_price = float(close_arr[-1])
    price_up = cur_price > price_10_ago

    if price_up and obv_trend == "上升":
        result["status"] = "confirmed_up"
        result["status_label"] = "OBV 与价格同步上升"
        result["detail"] = (
            "OBV 持续上升且价格同步上涨：量价配合良好，上升趋势确认。"
            "有资金持续流入配合，涨势健康可信。"
        )
    elif not price_up and obv_trend == "下降":
        result["status"] = "confirmed_down"
        result["status_label"] = "OBV 与价格同步下降"
        result["detail"] = "OBV 与价格同步下降，下跌趋势中资金持续流出，趋势偏空。"
    elif price_up and obv_trend != "上升":
        result["status"] = "obv_divergence_warning"
        result["status_label"] = "OBV 未配合价格上行"
        result["detail"] = (
            f"价格上涨但 OBV 趋势为'{obv_trend}'：OBV 未跟随价格创新高——"
            "这是顶背离信号，上涨缺乏资金支持。关注 OBV 能否跟上。"
        )
    elif not price_up and obv_trend != "下降":
        result["status"] = "obv_divergence_bottom"
        result["status_label"] = "OBV 先行企稳"
        result["detail"] = (
            f"价格下跌或盘整但 OBV 趋势为'{obv_trend}'：OBV 未跟随价格创新低——"
            "可能资金在悄悄吸筹（OBV 先行突破），是前瞻性的看涨信号。"
        )
    else:
        result["status"] = "neutral"
        result["status_label"] = "OBV 关系正常"
        result["detail"] = "OBV 与价格关系正常，无明显背离。"

    # OBV 是否创新高/低
    obv_max_20 = float(np.max(obv_arr[-20:])) if len(obv_arr) >= 20 else float(np.max(obv_arr))
    obv_min_20 = float(np.min(obv_arr[-20:])) if len(obv_arr) >= 20 else float(np.min(obv_arr))

    result["obv_at_high"] = cur_obv >= obv_max_20 * 0.98
    result["obv_at_low"] = cur_obv <= obv_min_20 * 1.02

    if result["obv_at_high"] and not price_up:
        result["detail"] += " OBV 接近20日高点但价格未同步——可能是聪明钱先行进场（OBV先行突破），这是最有价值的量价信号之一（★★★★★）。"

    result["summary"] = _obv_summary(result)
    result["checklist"] = _obv_checklist(result)
    return result


def _obv_summary(r: dict) -> str:
    mapping = {
        "confirmed_up": "OBV 与价格同步上升，趋势健康，资金持续流入。",
        "confirmed_down": "OBV 与价格同步下降，趋势偏空，资金持续流出。",
        "obv_divergence_warning": "OBV 未配合价格上行，顶背离预警，上涨动能存疑。",
        "obv_divergence_bottom": "OBV 先行企稳，可能资金在悄悄吸筹，关注反转机会。",
    }
    return mapping.get(r.get("status", ""), "OBV 与价格关系正常，无明显背离。")


def _obv_checklist(r: dict) -> list:
    items = []
    status = r.get("status", "")
    if status == "confirmed_up":
        items.append("OBV 配合上涨：趋势健康，可顺势持有，止损沿均线上移")
    elif status == "obv_divergence_warning":
        items.append("OBV 顶背离：不宜追高，已有的多头仓位收紧止损")
    elif status == "obv_divergence_bottom":
        items.append("OBV 先行企稳：关注但不急于入场，等价格突破确认")
    elif status == "confirmed_down":
        items.append("OBV 同步下降：下跌趋势中，不宜逆势做多")
    else:
        items.append("OBV 中性：作为辅助参考，不作为主要决策依据")
    if r.get("obv_at_high"):
        items.append("OBV 近20日高点：若价格未同步创新高，是OBV先行突破的强烈做多信号")
    return items


# ── 形态识别 ─────────────────────────────────────────────────────────────────

def _interpret_pattern(df: pd.DataFrame) -> dict:
    """量价形态识别：吸筹/派发/高潮/整理"""
    result = {}

    has_score = "pattern_score_sum" in df.columns
    has_climax_buy = "pattern_climax_buy" in df.columns
    has_climax_sell = "pattern_climax_sell" in df.columns

    if not has_score:
        return {"status": "data_insufficient", "status_label": "数据不足", "summary": "形态数据不可用", "detail": "", "checklist": []}

    score_sum = float(df["pattern_score_sum"].iloc[-1]) if len(df) > 0 else 0
    climax_buy = int(df["pattern_climax_buy"].iloc[-1]) == 1 if has_climax_buy else False
    climax_sell = int(df["pattern_climax_sell"].iloc[-1]) == 1 if has_climax_sell else False

    # 近10日量价趋势：涨缩量日数 vs 跌放量日数
    recent = df.iloc[-10:] if len(df) >= 10 else df
    if "price_change" in recent.columns and "volume_ratio" in recent.columns:
        up_shrink = int(((recent["price_change"] > 0) & (recent["volume_ratio"] < 1.0)).sum())
        down_expand = int(((recent["price_change"] < 0) & (recent["volume_ratio"] >= 1.0)).sum())
        up_expand = int(((recent["price_change"] > 0) & (recent["volume_ratio"] >= 1.0)).sum())
        down_shrink = int(((recent["price_change"] < 0) & (recent["volume_ratio"] < 1.0)).sum())
    else:
        up_shrink = down_expand = up_expand = down_shrink = 0

    result["score_sum"] = round(score_sum, 1)
    result["up_expand_days"] = up_expand
    result["down_shrink_days"] = down_shrink
    result["up_shrink_days"] = up_shrink
    result["down_expand_days"] = down_expand

    # 形态判定
    if climax_buy:
        result["status"] = "climax_buy"
        result["status_label"] = "卖出高潮（潜在底部）"
        result["detail"] = (
            "恐慌暴跌后出现单日天量，可能是最后的恐慌盘割肉完毕、卖盘耗尽。"
            "这是潜在底部信号。但需要二次确认不创新低才可入场——"
            "不要在天量当天接盘，等缩量回调不创新低后再考虑。"
        )
    elif climax_sell:
        result["status"] = "climax_sell"
        result["status_label"] = "买入高潮（潜在顶部）"
        result["detail"] = (
            "长期上涨后出现单日天量阳线，但价格可能已无法继续上行。"
            "最后的追涨盘入场完毕、买盘耗尽。这是减仓或清仓信号，不是加仓信号。"
            "常见误区：散户看到天量阳线追入，但这是最大买家已经进场的标志。"
        )
    elif score_sum >= 3.0:
        result["status"] = "accumulation"
        result["status_label"] = "吸筹建仓"
        result["detail"] = (
            f"近10日形态评分 {score_sum:.1f}（≥3.0）：整体呈现「涨放量、跌缩量」的健康格局。"
            f"近10日中，涨放量{up_expand}天、跌缩量{down_shrink}天，"
            "资金在悄悄进场。价格可能处于底部区域，等放量突破横盘区间上沿确认后再入场。"
        )
    elif score_sum <= -3.0:
        result["status"] = "distribution"
        result["status_label"] = "派发出货"
        result["detail"] = (
            f"近10日形态评分 {score_sum:.1f}（≤-3.0）：整体呈现「涨缩量、跌放量」的危险格局。"
            f"近10日中，涨缩量{up_shrink}天、跌放量{down_expand}天，"
            "这是最危险的结构之一——主力在悄然出货。建议立即减仓至少一半，"
            "若跌破横盘下沿全部清仓。不要抄底，派发之后通常有深度回调。"
        )
    elif abs(score_sum) < 1.5:
        result["status"] = "contraction"
        result["status_label"] = "缩量整理"
        result["detail"] = (
            f"近10日形态评分接近0（{score_sum:.1f}）：市场处于缩量整理阶段，"
            "方向不明。此时不宜重仓押注方向，等待放量选择方向后再顺势操作。"
            "中继整理形态中持仓者应持币或持股不动，不追涨不杀跌。"
        )
    else:
        result["status"] = "transitioning"
        result["status_label"] = "形态过渡中"
        direction = "偏向吸筹" if score_sum > 0 else "偏向派发"
        result["detail"] = (
            f"近10日形态评分 {score_sum:.1f}：{direction}，但尚未达到明确阈值。"
            "形态正在形成中，需继续观察后续量价结构。"
        )

    result["summary"] = _pattern_summary(result)
    result["checklist"] = _pattern_checklist(result)
    return result


def _pattern_summary(r: dict) -> str:
    mapping = {
        "accumulation": "吸筹建仓形态：涨放量跌缩量，资金悄悄进场，等待突破确认。",
        "distribution": "派发出货形态：涨缩量跌放量，主力悄然出货，这是最危险的结构。",
        "climax_buy": "卖出高潮：恐慌盘出尽，潜在底部信号，等待二次确认。",
        "climax_sell": "买入高潮：买盘耗尽，潜在顶部信号，应考虑减仓。",
        "contraction": "缩量整理：方向不明，以观望为主。",
    }
    return mapping.get(r.get("status", ""), "形态过渡中，需继续观察量价结构变化。")


def _pattern_checklist(r: dict) -> list:
    items = []
    status = r.get("status", "")
    if status == "accumulation":
        items.append("吸筹区：不急于入场，等放量突破横盘上沿确认后进场更安全")
        items.append("虽然牺牲底部5-10%，但安全系数大幅提升")
    elif status == "distribution":
        items.append("派发区：立即检查仓位——如持有该股应立即减仓至少一半")
        items.append("若跌破横盘区间下沿，全部清仓离场")
        items.append("不要抄底：派发之后通常有深度回调")
    elif status == "climax_buy":
        items.append("卖出高潮：关注但不急于接盘，等缩量二次确认不创新低")
    elif status == "climax_sell":
        items.append("买入高潮：减仓或清仓信号——最大的买家已进场，后续难有更大买盘")
    elif status == "contraction":
        items.append("缩量整理：持币或持股不动，不预判方向，等放量突破再顺势操作")
    else:
        items.append("形态过渡中：继续观察，耐心等待明确形态形成")
    return items


# ── 操作建议 ─────────────────────────────────────────────────────────────────

def _trading_advice(relation: dict, divergence: dict, breakout: dict,
                    pullback: dict, obv_analysis: dict, pattern: dict,
                    df: pd.DataFrame) -> dict:
    """综合量价分析生成操作建议"""
    result = {}

    # 收集所有买入信号和卖出信号
    buy_signals = []
    sell_signals = []

    if divergence.get("status") == "bottom_divergence":
        buy_signals.append("底背离")
    if divergence.get("status") == "top_divergence":
        sell_signals.append("顶背离")

    if breakout.get("is_breakout"):
        buy_signals.append("放量突破")
    if breakout.get("level") == "extreme" and breakout.get("is_breakout"):
        sell_signals.append("天量警惕")

    if pullback.get("status") == "active":
        buy_signals.append("缩量回调")
    elif pullback.get("status") == "bearish_pullback":
        sell_signals.append("放量下跌")

    if obv_analysis.get("status") == "obv_divergence_warning":
        sell_signals.append("OBV顶背离")
    if obv_analysis.get("status") == "obv_divergence_bottom":
        buy_signals.append("OBV底背离")

    if pattern.get("status") == "distribution":
        sell_signals.append("派发出货")
    elif pattern.get("status") == "climax_sell":
        sell_signals.append("买入高潮")
    elif pattern.get("status") == "accumulation":
        buy_signals.append("吸筹形态")
    elif pattern.get("status") == "climax_buy":
        buy_signals.append("卖出高潮")

    result["buy_signals"] = buy_signals
    result["sell_signals"] = sell_signals

    # 共振计数
    resonance_count = 0
    if divergence.get("status") in ("bottom_divergence", "top_divergence"):
        resonance_count += 1
    if breakout.get("level") in ("strong", "moderate", "extreme"):
        resonance_count += 1
    if pullback.get("status") == "active":
        resonance_count += 1
    if obv_analysis.get("status") in ("confirmed_up", "confirmed_down",
                                       "obv_divergence_warning", "obv_divergence_bottom"):
        resonance_count += 1
    if pattern.get("status") not in ("data_insufficient", "contraction", "transitioning"):
        resonance_count += 1

    result["resonance_count"] = resonance_count

    # 入场建议
    if len(buy_signals) >= 2 or (len(buy_signals) >= 1 and resonance_count >= 2):
        result["entry_ready"] = True
        result["entry_advice"] = (
            f"多个买入信号共振：{'、'.join(buy_signals)}。"
            "量价结构偏向多头，可在确认当日收盘后入场。"
            "注意：即使信号共振也不应全仓——每笔风险不超过总账户2%。"
        )
    elif len(sell_signals) >= 2 or (len(sell_signals) >= 1 and resonance_count >= 2):
        result["entry_ready"] = False
        result["entry_advice"] = (
            f"多个卖出信号共振：{'、'.join(sell_signals)}。"
            "量价结构偏向空头，不宜做多。若持有多头仓位应考虑减仓或平仓。"
        )
    else:
        result["entry_ready"] = False
        result["entry_advice"] = (
            "当前量价信号不足或方向混搭，市场可能处于混沌状态。"
            "建议继续观望，等待更多信号确认后再行动。"
            "缩量整理时以观望为主，不预判方向。"
        )

    # 出场建议
    if len(sell_signals) >= 2:
        result["exit_ready"] = True
        result["exit_advice"] = "多个卖出信号共振，若持有多头仓位应果断减仓或清仓。不要等所有信号都确认后才行动。"
    elif len(sell_signals) >= 1:
        result["exit_ready"] = True
        result["exit_advice"] = "存在卖出信号，密切关注后续是否强化。建议收紧移动止损。"
    else:
        result["exit_ready"] = False
        result["exit_advice"] = "暂无明显出场信号，持仓者可继续持有，但需设好移动止损。"

    # 止损建议
    close_arr = df["close"].values
    if len(close_arr) >= 20:
        ma20 = float(np.mean(close_arr[-20:]))
        if buy_signals:
            result["stop_loss_suggestion"] = (
                f"建议止损位设在 MA20（约 ¥{ma20:.2f}）下方 2-3% "
                "或近期低点下方。成交量策略的止损比均线策略更宽，"
                "因量价信号可能有一定提前量。"
            )
        elif sell_signals:
            result["stop_loss_suggestion"] = (
                "若做空，止损设在近期高点上方 2-3%。空头仓位风险较高，建议小仓位试探。"
            )
        else:
            result["stop_loss_suggestion"] = "信号不明时不宜持仓，止损参考 MA20 下方。"
    else:
        result["stop_loss_suggestion"] = "数据不足，无法给出具体止损建议。"

    result["summary"] = result.get("entry_advice", "观望为主")
    result["checklist"] = _advice_checklist(result, buy_signals, sell_signals, resonance_count)
    return result


def _advice_checklist(result: dict, buy_signals: list, sell_signals: list, resonance: int) -> list:
    items = []
    if result.get("entry_ready"):
        items.append("入场前：等待当日收盘确认，避免盘中假突破")
        items.append("仓位管理：共振信号可适度放大但不超过3%风险")
        items.append("入场后：沿MA20移动止损，保护已有利润")
    else:
        items.append("观望：不急于入场，等待信号改善")

    if result.get("exit_ready") and sell_signals:
        items.append(f"关注卖出信号：{'、'.join(sell_signals)}")

    if resonance >= 3:
        items.append("多维度共振（≥3）：信号可靠性较高，可重点关注操作机会")
    elif resonance >= 2:
        items.append("轻量共振（2维）：信号有一定参考价值，但仍需谨慎")

    items.append("牛市怕放量（下跌放量是出货），熊市怕缩量（反弹缩量是诱多）")
    return items
