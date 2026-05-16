"""三重确认策略 — 结构化中文解读"""

import pandas as pd
import numpy as np


def interpret_triple_confirm_all(df: pd.DataFrame) -> dict:
    """
    对三重确认策略的结果进行七维结构化中文解读。

    Returns:
        {signal_grade, macd_confirm, rsi_confirm, volume_confirm,
         auxiliary, exit_triggers, trading_advice}
    """
    if len(df) == 0:
        return {"error": "数据为空"}

    required_cols = ["close", "volume", "macd", "macd_signal", "macd_histogram",
                     "rsi", "adx", "volume_ratio", "ma50", "signal_grade"]
    for col in required_cols:
        if col not in df.columns:
            return {"error": f"缺少必要列: {col}，请先运行 TripleConfirmStrategy.generate_signals()"}

    latest = df.iloc[-1]
    grade = str(latest.get("signal_grade", "NONE"))
    base_grade = grade.split("_")[0]

    return {
        "signal_grade": _interpret_signal_grade(grade, base_grade, df),
        "macd_confirm": _interpret_macd_dimension(df, latest),
        "rsi_confirm": _interpret_rsi_dimension(df, latest),
        "volume_confirm": _interpret_volume_dimension(df, latest),
        "auxiliary": _interpret_auxiliary(df, latest, base_grade),
        "exit_triggers": _interpret_exit_triggers(df, latest),
        "trading_advice": _interpret_trading_advice(df, latest, base_grade, grade),
    }


def _interpret_signal_grade(grade: str, base_grade: str, df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    is_buy = latest.get("buy_signal") == 1

    grade_descriptions = {
        "S": "三重共振高确信信号：MACD背离 + RSI背离 + 放量阳线确认 + MACD交叉，可靠性约70-75%",
        "A": "标准入场信号：MACD交叉 + RSI配合 + 成交量确认，可靠性约60-65%",
        "B": "试探信号：MACD交叉 + RSI配合（成交量未确认），可靠性约50-55%",
        "C": "仅观察信号：仅MACD交叉，可靠性约40-45%，不推荐直接交易",
    }

    grade_actions = {
        "S": "正常或略大仓位（风险不超过3%），止损在背离低点下方",
        "A": "正常仓位，标准止损",
        "B": "轻仓试探（正常仓位50%），止损严格",
        "C": "仅加入观察列表，不交易。等待RSI和成交量确认升级为B级以上",
    }

    description = grade_descriptions.get(base_grade, "未知信号等级")
    action = grade_actions.get(base_grade, "")

    has_filter = "_adx_filtered" in grade or "_trend_weak" in grade
    filter_notes = []
    if "_adx_filtered" in grade:
        filter_notes.append("ADX < 20，市场处于震荡/无趋势状态，信号可靠性降低")
    if "_trend_weak" in grade:
        filter_notes.append("MA50 方向不利，仅做反弹不做趋势单")

    direction = "做多" if is_buy else "做空"
    signal_count = int((df["signal_grade"] != "NONE").sum())

    return {
        "status": base_grade.lower() if not has_filter else "filtered",
        "status_label": grade,
        "direction": direction,
        "description": description,
        "action": action,
        "has_filters": has_filter,
        "filter_notes": filter_notes,
        "history_signal_count": signal_count,
        "summary": f"{direction}信号 {grade}",
        "detail": f"{description}{'；但经辅助过滤: ' + '; '.join(filter_notes) if filter_notes else ''}",
        "checklist": [
            "确认信号等级和方向" + (" ✓" if base_grade in ("S", "A") else " ⚠"),
            "检查辅助过滤状态" + (" ✓" if not has_filter else " ⚠"),
            "确认仓位建议" + " ✓",
            "设置止损位" + " ✓",
        ],
    }


def _interpret_macd_dimension(df: pd.DataFrame, latest: pd.Series) -> dict:
    macd_val = _safe_float(latest.get("macd"))
    sig_val = _safe_float(latest.get("macd_signal"))
    hist_val = _safe_float(latest.get("macd_histogram"))
    has_cross_buy = latest.get("macd_bullish_cross") == 1
    has_cross_sell = latest.get("macd_bearish_cross") == 1
    has_bottom_div = latest.get("macd_bottom_divergence") == 1
    has_top_div = latest.get("macd_top_divergence") == 1

    if macd_val is None:
        return {"status": "unknown", "summary": "MACD数据缺失"}

    # 位置判断
    if macd_val > 0 and macd_val > sig_val:
        position = "多头趋势"
        position_label = "bullish"
    elif macd_val < 0 and macd_val < sig_val:
        position = "空头趋势"
        position_label = "bearish"
    else:
        position = "震荡/转势"
        position_label = "oscillating"

    # 交叉
    cross_detail = ""
    if has_cross_buy:
        cross_detail = "MACD金叉（MACD线上穿信号线），多头启动信号"
    elif has_cross_sell:
        cross_detail = "MACD死叉（MACD线下穿信号线），空头启动信号"
    else:
        cross_detail = "无最新交叉信号"

    # 背离
    div_detail = ""
    if has_bottom_div:
        div_detail = "检测到MACD底背离（价格新低+MACD未新低），最可靠的底部预警"
    elif has_top_div:
        div_detail = "检测到MACD顶背离（价格新高+MACD未新高），最可靠的顶部预警"

    # 柱状图动量
    prev_hist = _safe_float(df["macd_histogram"].iloc[-2]) if len(df) > 1 else None
    if hist_val is not None and prev_hist is not None:
        if abs(hist_val) > abs(prev_hist):
            momentum = "MACD柱扩大，动量增强"
        else:
            momentum = "MACD柱缩小，动量减弱（警戒信号）"
    else:
        momentum = ""

    return {
        "status": position_label,
        "status_label": position,
        "macd": round(macd_val, 4) if macd_val else None,
        "signal_line": round(sig_val, 4) if sig_val else None,
        "histogram": round(hist_val, 4) if hist_val else None,
        "has_cross": has_cross_buy or has_cross_sell,
        "cross_detail": cross_detail,
        "has_divergence": has_bottom_div or has_top_div,
        "divergence_detail": div_detail,
        "momentum": momentum,
        "summary": f"MACD {position}",
        "detail": f"MACD={macd_val:.4f}, 信号线={sig_val:.4f}, 柱={hist_val:.4f}。{cross_detail}{'；' + div_detail if div_detail else ''}{'；' + momentum if momentum else ''}",
        "checklist": [
            "MACD方向与信号方向一致" + (" ✓" if (has_cross_buy and position_label == "bullish") or (has_cross_sell and position_label == "bearish") else " ⚠"),
            "无MACD背离反向警示" + (" ✓" if not (has_bottom_div and has_cross_sell) else " ⚠"),
        ],
    }


def _interpret_rsi_dimension(df: pd.DataFrame, latest: pd.Series) -> dict:
    rsi_val = _safe_float(latest.get("rsi"))
    if rsi_val is None:
        return {"status": "unknown", "summary": "RSI数据缺失"}

    if rsi_val >= 70:
        zone = "超买区"
        zone_label = "overbought"
    elif rsi_val <= 30:
        zone = "超卖区"
        zone_label = "oversold"
    elif 40 <= rsi_val <= 60:
        zone = "中性区"
        zone_label = "neutral"
    elif rsi_val > 60:
        zone = "偏强区"
        zone_label = "strong"
    else:
        zone = "偏弱区"
        zone_label = "weak"

    # RSI 方向
    prev_rsi = _safe_float(df["rsi"].iloc[-2]) if len(df) > 1 else None
    if prev_rsi is not None:
        direction = "向上" if rsi_val > prev_rsi else "向下"
    else:
        direction = "未知"

    has_bottom_div = latest.get("rsi_bottom_divergence") == 1
    has_top_div = latest.get("rsi_top_divergence") == 1

    div_detail = ""
    if has_bottom_div:
        div_detail = "检测到RSI底背离"
    elif has_top_div:
        div_detail = "检测到RSI顶背离"

    # 趋势强度诊断
    health = ""
    if 40 <= rsi_val <= 80:
        health = "健康上升区间，适宜持仓"
    elif 20 <= rsi_val <= 60:
        health = "健康下降区间，适宜持币"

    return {
        "status": zone_label,
        "status_label": zone,
        "value": round(rsi_val, 1),
        "direction": direction,
        "has_divergence": has_bottom_div or has_top_div,
        "divergence_detail": div_detail,
        "health": health,
        "summary": f"RSI {rsi_val:.1f} ({zone})",
        "detail": f"RSI={rsi_val:.1f}，处于{zone}，方向{direction}。{div_detail}{'；' + health if health else ''}",
        "checklist": [
            "RSI未超买" + (" ✓" if rsi_val < 75 else " ⚠ RSI超买，谨慎追高"),
            "RSI未超卖" + (" ✓" if rsi_val > 25 else " ⚠ RSI超卖，注意反弹"),
        ],
    }


def _interpret_volume_dimension(df: pd.DataFrame, latest: pd.Series) -> dict:
    vol_ratio = _safe_float(latest.get("volume_ratio"))
    has_shrink = latest.get("volume_shrink_pattern") == 1

    if vol_ratio is None:
        return {"status": "unknown", "summary": "成交量数据缺失"}

    if vol_ratio >= 3.0:
        level = "天量"
        level_label = "extreme"
    elif vol_ratio >= 2.0:
        level = "显著放量"
        level_label = "high"
    elif vol_ratio >= 1.0:
        level = "正常"
        level_label = "normal"
    else:
        level = "缩量"
        level_label = "low"

    pattern_detail = ""
    if has_shrink:
        pattern_detail = "检测到'缩量止跌+今日放量起涨'格局，资金介入明显"

    return {
        "status": level_label,
        "status_label": level,
        "volume_ratio": round(vol_ratio, 2),
        "has_shrink_pattern": has_shrink,
        "pattern_detail": pattern_detail,
        "summary": f"量比 {vol_ratio:.2f} ({level})",
        "detail": f"量比={vol_ratio:.2f}（{level}）。{pattern_detail}",
        "checklist": [
            "成交量确认信号" + (" ✓" if vol_ratio >= 1.0 else " ⚠ 缩量，信号可靠性降低"),
            "无异常放量出货" + (" ✓" if vol_ratio < 3.0 else " ⚠ 天量需警惕出货"),
        ],
    }


def _interpret_auxiliary(df: pd.DataFrame, latest: pd.Series, base_grade: str) -> dict:
    adx_val = _safe_float(latest.get("adx"))
    ma50_val = _safe_float(latest.get("ma50"))
    ma50_dir_val = latest.get("ma50_direction", 0)
    weekly_confirm = latest.get("weekly_macd_bullish") == 1
    close = _safe_float(latest.get("close"))

    # ADX 趋势强度
    if adx_val is not None:
        if adx_val >= 40:
            adx_label = "极强趋势"
        elif adx_val >= 25:
            adx_label = "趋势明确"
        elif adx_val >= 20:
            adx_label = "趋势形成中"
        else:
            adx_label = "震荡/无趋势"
    else:
        adx_label = "N/A"

    # MA50
    ma50_direction_str = "向上" if ma50_dir_val == 1 else ("向下" if ma50_dir_val == -1 else "平坦")
    if close is not None and ma50_val is not None and ma50_val > 0:
        above_ma50 = "上方" if close > ma50_val else "下方"
    else:
        above_ma50 = "N/A"

    # 周线
    weekly_str = "周线MACD看涨，与日线信号共振" if weekly_confirm else "周线未确认，信号强度降低"

    # S级 + 周线确认 = 满分
    if base_grade in ("S", "A") and weekly_confirm:
        quality = "满分（周线+日线共振）"
    elif base_grade == "S":
        quality = "高确信（日线，周线待确认）"
    elif base_grade == "A":
        quality = "标准（日线确认，周线未共振）"
    elif base_grade == "B":
        quality = "试探（等待更多确认）"
    else:
        quality = "观察级"

    return {
        "adx": round(adx_val, 1) if adx_val else None,
        "adx_label": adx_label,
        "ma50": round(ma50_val, 2) if ma50_val else None,
        "ma50_direction": ma50_direction_str,
        "ma50_position": above_ma50,
        "weekly_confirm": weekly_confirm,
        "weekly_detail": weekly_str,
        "quality": quality,
        "summary": f"ADX={adx_val:.1f}({adx_label}), MA50{ma50_direction_str}",
        "detail": f"ADX={adx_val:.1f}（{adx_label}）；MA50={ma50_val:.2f}，方向{ma50_direction_str}，价格在MA50{above_ma50}；{weekly_str}。综合质量：{quality}",
        "checklist": [
            "ADX趋势明确" + (" ✓" if adx_val is not None and adx_val >= 20 else " ⚠ 震荡市，信号易假"),
            "MA50方向有利" + (" ✓" if ma50_dir_val >= 0 else " ⚠ MA50向下，仅做反弹"),
            "周线确认" + (" ✓" if weekly_confirm else " ○ 未确认"),
        ],
    }


def _interpret_exit_triggers(df: pd.DataFrame, latest: pd.Series) -> dict:
    triggers = []
    trigger_labels = {
        "exit_trigger_1": "MACD死叉/金叉出场（最高优先级）",
        "exit_trigger_2": "RSI背离出场",
        "exit_trigger_3": "RSI超买后回落出场",
        "exit_trigger_4": "价涨量缩连续3日出场",
        "exit_trigger_5": "价格跌破MA20出场（辅助）",
    }

    for col, label in trigger_labels.items():
        if latest.get(col, 0) == 1:
            triggers.append(label)

    active = len(triggers) > 0
    return {
        "active": active,
        "triggers": triggers,
        "count": len(triggers),
        "summary": f"{len(triggers)}个出场条件触发" if active else "无出场条件触发",
        "detail": "；".join(triggers) if triggers else "当前无出场条件触发，建议继续持仓观察",
        "checklist": [
            f"{'⚠' if active else '✓'} 出场条件: {'已触发' if active else '未触发'}",
        ],
    }


def _interpret_trading_advice(df: pd.DataFrame, latest: pd.Series, base_grade: str, grade: str) -> dict:
    is_buy = latest.get("buy_signal") == 1
    close = _safe_float(latest.get("close"))
    rsi_val = _safe_float(latest.get("rsi"))
    adx_val = _safe_float(latest.get("adx"))

    has_filter = "_adx_filtered" in grade or "_trend_weak" in grade

    if is_buy:
        if base_grade == "S" and not has_filter:
            entry_advice = "高确信做多信号，可正常或略大仓位入场。止损设在近期低点下方或1个ATR下方"
        elif base_grade == "A" and not has_filter:
            entry_advice = "标准做多信号，可正常仓位入场。等待次日开盘确认后执行"
        elif base_grade == "B" or has_filter:
            entry_advice = "试探性做多信号，建议轻仓或等待信号升级。MA50和成交量确认后再加仓"
        else:
            entry_advice = "仅观察信号，不推荐入场。等待RSI配合和成交量确认升级"
    else:
        if base_grade == "S" and not has_filter:
            entry_advice = "高确信做空信号，可正常仓位做空。止损设在近期高点上方"
        elif base_grade == "A" and not has_filter:
            entry_advice = "标准做空信号，可正常仓位入场"
        elif base_grade == "B" or has_filter:
            entry_advice = "试探性做空信号，建议轻仓或等待信号升级"
        else:
            entry_advice = "仅观察信号，不推荐入场做空"

    # 出场建议
    exit_triggers_active = sum(1 for col in [f"exit_trigger_{i}" for i in range(1, 6)]
                               if latest.get(col, 0) == 1)
    if exit_triggers_active > 0:
        exit_advice = f"已有{exit_triggers_active}个出场条件触发，建议减仓或平仓"
    else:
        exit_advice = "持仓观察，设置止损保护"

    # RSI 超买过滤
    rsi_warning = ""
    if is_buy and rsi_val is not None and rsi_val > 75:
        rsi_warning = "⚠ RSI > 75，价格已处于超买区，不建议在此时追高做多。等RSI回落到50-60区间再考虑"

    return {
        "entry_ready": base_grade in ("S", "A") and not has_filter,
        "entry_advice": entry_advice,
        "exit_ready": exit_triggers_active > 0,
        "exit_advice": exit_advice,
        "rsi_warning": rsi_warning,
        "stop_loss_suggestion": f"建议止损设在入场价下方{'1.5' if base_grade == 'S' else '1'}个ATR或近期低点",
        "summary": entry_advice,
        "detail": f"{entry_advice}。{exit_advice}{'。' + rsi_warning if rsi_warning else ''}",
        "checklist": [
            "入场条件满足" + (" ✓" if base_grade in ("S", "A") and not has_filter else " ○"),
            "无辅助过滤降级" + (" ✓" if not has_filter else " ⚠"),
            "RSI未极端超买" + (" ✓" if not rsi_warning else " ⚠"),
            "出场条件未触发" + (" ✓" if exit_triggers_active == 0 else " ⚠"),
        ],
    }


def _safe_float(val) -> float | None:
    """安全转换为 float"""
    if val is None:
        return None
    try:
        v = float(val)
        return v if pd.notna(v) and not np.isinf(v) else None
    except (ValueError, TypeError):
        return None
