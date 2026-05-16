"""KDJ + 布林带 + ATR 波动率策略 — 结构化中文解读"""

import pandas as pd
import numpy as np


def interpret_kdj_bb_atr_all(df: pd.DataFrame) -> dict:
    """
    对 KDJ+布林带+ATR 策略的结果进行七维结构化中文解读。

    Returns:
        {environment, signal_grade, kdj_dimension, bollinger_dimension,
         atr_dimension, exit_triggers, trading_advice}
    """
    if len(df) == 0:
        return {"error": "数据为空"}

    required_cols = ["close", "volume", "kdj_k", "kdj_d", "kdj_j", "atr",
                     "boll_up", "boll_down", "ma_mid", "bandwidth",
                     "volume_ratio", "signal_grade", "environment"]
    for col in required_cols:
        if col not in df.columns:
            return {"error": f"缺少必要列: {col}，请先运行 KdjBollingerAtrStrategy.generate_signals()"}

    latest = df.iloc[-1]
    grade = str(latest.get("signal_grade", "NONE"))
    base_grade = grade.split("_")[0]
    env = str(latest.get("environment", "unknown"))

    return {
        "environment": _interpret_environment(df, latest, env),
        "signal_grade": _interpret_signal_grade(grade, base_grade, latest, df),
        "kdj_dimension": _interpret_kdj(df, latest),
        "bollinger_dimension": _interpret_bollinger(df, latest),
        "atr_dimension": _interpret_atr(df, latest),
        "exit_triggers": _interpret_exit_triggers(df, latest),
        "trading_advice": _interpret_trading_advice(df, latest, base_grade, grade, env),
    }


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        v = float(val)
        return v if pd.notna(v) and not np.isinf(v) else None
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════
# 1. 环境解读
# ═══════════════════════════════════════════════════════════════

def _interpret_environment(df: pd.DataFrame, latest: pd.Series, env: str) -> dict:
    mid = _safe_float(latest.get("ma_mid"))
    bw = _safe_float(latest.get("bandwidth"))
    atr_val = _safe_float(latest.get("atr"))

    env_labels = {
        "range": "震荡格局",
        "trend": "趋势市场",
        "squeeze": "蓄势突破",
        "unknown": "判定中",
    }

    if env == "range":
        mode = "区间回归交易"
        mode_detail = "价格在布林带上下轨间规律波动，以触轨回归策略为主。在趋势里不做回归，在震荡里不追突破。"
        caution = "注意：震荡环境中轨是可靠目标，但需警惕突破启动。ATR突升=变盘预警。"
    elif env == "trend":
        mode = "顺势回调入场"
        mode_detail = "价格沿布林带中轨或上/下轨持续运行，放弃触轨反向交易，只做顺势回调到中轨附近入场。"
        caution = "注意：KDJ在趋势中会持续钝化（J>100不回调），不要据此逆势。中轨方向是第一过滤器。"
    elif env == "squeeze":
        mode = "突破跟进"
        mode_detail = "布林带带宽收缩到历史低位，市场在积蓄能量。等待第一根突破K线收盘确认后入场，不做区间交易。"
        caution = "注意：压缩越久，爆发越猛。突破后可能直接穿过一个轨道，止损需宽松（2×ATR）。"
    else:
        mode = "等待环境确认"
        mode_detail = "当前指标数据不足以判定环境，建议观望。"
        caution = ""

    # 斜率检测
    slope_desc = "未知"
    if mid is not None and len(df) > 5:
        prev_mid = _safe_float(df["ma_mid"].iloc[-6])
        if prev_mid and prev_mid > 0:
            slope_pct = (mid - prev_mid) / prev_mid * 100
            if abs(slope_pct) < 0.5:
                slope_desc = f"走平 ({slope_pct:+.2f}%)"
            elif slope_pct > 0:
                slope_desc = f"向上 ({slope_pct:+.2f}%)"
            else:
                slope_desc = f"向下 ({slope_pct:+.2f}%)"

    # ATR趋势
    atr_trend = "未知"
    if atr_val is not None and len(df) > 5:
        prev_atr = _safe_float(df["atr"].iloc[-6])
        if prev_atr and prev_atr > 0:
            atr_chg = atr_val / prev_atr
            if atr_chg > 1.2:
                atr_trend = "扩张中（波动加剧）"
            elif atr_chg < 0.85:
                atr_trend = "收缩中（波动减小）"
            else:
                atr_trend = "稳定"

    # 周线确认
    weekly_bull = latest.get("weekly_bb_bullish") == 1
    weekly_bear = latest.get("weekly_bb_bearish") == 1
    if weekly_bull:
        weekly_note = "周线布林带中轨向上，仅做多不做空"
    elif weekly_bear:
        weekly_note = "周线布林带中轨向下，仅做空不做多"
    else:
        weekly_note = "周线方向未确认"

    return {
        "status": env,
        "status_label": env_labels.get(env, "未知"),
        "mode": mode,
        "mode_detail": mode_detail,
        "caution": caution,
        "mid_slope": slope_desc,
        "atr_trend": atr_trend,
        "bandwidth": round(bw, 2) if bw else None,
        "weekly_note": weekly_note,
        "summary": f"当前市场: {env_labels.get(env, '未知')}，建议模式: {mode}",
        "detail": f"中轨斜率={slope_desc}，带宽={bw:.2f}%，ATR趋势={atr_trend}。" + mode_detail + caution,
        "checklist": [
            "确认当前环境类型" + " ✓",
            "选择对应交易模式" + " ✓",
            f"周线方向过滤: {weekly_note}" + (" ✓" if weekly_bull or weekly_bear else " ○"),
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 2. 信号等级解读
# ═══════════════════════════════════════════════════════════════

def _interpret_signal_grade(grade: str, base_grade: str, latest: pd.Series, df: pd.DataFrame) -> dict:
    is_buy = latest.get("buy_signal") == 1

    grade_descriptions = {
        "S": "全系统共振信号：布林带Squeeze突破 + KDJ背离 + ATR扩张 + 成交量确认，可靠性约70-75%",
        "A": "标准入场信号：布林带触轨 + KDJ金叉/死叉 + ATR稳定 + 中轨走平（震荡环境确认），可靠性约60-65%",
        "B": "试探信号：布林带触轨 + KDJ确认（ATR未确认），可靠性约50-55%",
        "C": "仅观察信号：仅单指标触轨或仅KDJ交叉，可靠性约40-45%，不推荐直接交易",
    }

    grade_actions = {
        "S": "重仓（风险2-2.5%），止损用2×ATR或反向轨道",
        "A": "标准仓位（风险1.5%），止损用1.5×ATR",
        "B": "轻仓试探（风险0.5-1%），止损严格",
        "C": "仅加入观察列表，不交易。等待另一个指标确认升级为B级以上",
    }

    description = grade_descriptions.get(base_grade, "未知信号等级")
    action = grade_actions.get(base_grade, "")

    has_filter = "_weekly_against" in grade
    filter_notes = []
    if "_weekly_against" in grade:
        filter_notes.append("当前信号与周线布林带方向相悖，可靠性降低，仅做短线反弹/回调")

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
        "detail": f"{description}{'；但经周线过滤: ' + '; '.join(filter_notes) if filter_notes else ''}",
        "checklist": [
            "确认信号等级和方向" + (" ✓" if base_grade in ("S", "A") else " ⚠"),
            "检查周线过滤状态" + (" ✓" if not has_filter else " ⚠"),
            "确认仓位建议" + " ✓",
            "设置ATR动态止损" + " ✓",
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 3. KDJ 维度解读
# ═══════════════════════════════════════════════════════════════

def _interpret_kdj(df: pd.DataFrame, latest: pd.Series) -> dict:
    k_val = _safe_float(latest.get("kdj_k"))
    d_val = _safe_float(latest.get("kdj_d"))
    j_val = _safe_float(latest.get("kdj_j"))
    has_golden = latest.get("kdj_golden_cross") == 1
    has_death = latest.get("kdj_death_cross") == 1
    j_extreme_high = latest.get("kdj_j_extreme_high") == 1
    j_extreme_low = latest.get("kdj_j_extreme_low") == 1
    has_bottom_div = latest.get("kdj_bottom_divergence") == 1
    has_top_div = latest.get("kdj_top_divergence") == 1

    if k_val is None or d_val is None or j_val is None:
        return {"status": "unknown", "summary": "KDJ数据缺失"}

    # 区域判定
    if k_val > 80 and d_val > 70:
        zone = "超买区"
        zone_label = "overbought"
    elif k_val < 20 and d_val < 30:
        zone = "超卖区"
        zone_label = "oversold"
    elif 40 <= k_val <= 60:
        zone = "中性区"
        zone_label = "neutral"
    elif k_val > 60:
        zone = "偏强区"
        zone_label = "strong"
    else:
        zone = "偏弱区"
        zone_label = "weak"

    # J 值诊断
    if j_val > 100:
        j_note = "J > 100: K线快速远离D线，超买但动量加速中（非卖出信号而是关注信号）"
    elif j_val < 0:
        j_note = "J < 0: K线快速远离D线，超卖但动量加速中（非买入信号而是关注信号）"
    elif j_val > 80:
        j_note = "J值偏高区，关注拐头迹象"
    elif j_val < 20:
        j_note = "J值偏低区，关注拐头迹象"
    else:
        j_note = "J值中性"

    # KDJ 方向
    prev_j = _safe_float(df["kdj_j"].iloc[-2]) if len(df) > 1 else None
    if prev_j is not None:
        j_direction = "向上" if j_val > prev_j else "向下"
    else:
        j_direction = "未知"

    # 交叉
    cross_detail = ""
    if has_golden:
        cross_detail = "KDJ金叉（K线上穿D线），短线看涨信号"
    elif has_death:
        cross_detail = "KDJ死叉（K线下穿D线），短线看跌信号"
    else:
        cross_detail = "无最新交叉信号"

    # 背离
    div_detail = ""
    if has_bottom_div:
        div_detail = "检测到KDJ底背离（价格新低+D值未新低），可能的底部预警"
    elif has_top_div:
        div_detail = "检测到KDJ顶背离（价格新高+D值未新高），可能的顶部预警"
    if div_detail:
        div_detail += "；注意KDJ背离出现早，也常有假背离"

    return {
        "status": zone_label,
        "status_label": zone,
        "k": round(k_val, 2),
        "d": round(d_val, 2),
        "j": round(j_val, 2),
        "j_note": j_note,
        "j_direction": j_direction,
        "has_cross": has_golden or has_death,
        "cross_detail": cross_detail,
        "has_divergence": has_bottom_div or has_top_div,
        "divergence_detail": div_detail,
        "summary": f"KDJ K={k_val:.1f} D={d_val:.1f} J={j_val:.1f} ({zone})",
        "detail": f"K={k_val:.2f}, D={d_val:.2f}, J={j_val:.2f}，处于{zone}，J方向{j_direction}。{j_note}。{cross_detail}{'；' + div_detail if div_detail else ''}",
        "checklist": [
            "KDJ未在趋势中钝化" + (" ✓" if not (j_extreme_high and j_direction == "向上") else " ⚠ 趋势钝化中，忽略超买信号"),
            "KDJ未在趋势中钝化" + (" ✓" if not (j_extreme_low and j_direction == "向下") else " ⚠ 趋势钝化中，忽略超卖信号"),
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 4. 布林带维度解读
# ═══════════════════════════════════════════════════════════════

def _interpret_bollinger(df: pd.DataFrame, latest: pd.Series) -> dict:
    close = _safe_float(latest.get("close"))
    boll_up = _safe_float(latest.get("boll_up"))
    boll_mid = _safe_float(latest.get("ma_mid"))
    boll_down = _safe_float(latest.get("boll_down"))
    bw = _safe_float(latest.get("bandwidth"))

    touch_upper = latest.get("bb_touch_upper") == 1
    touch_lower = latest.get("bb_touch_lower") == 1
    pierce_upper = latest.get("bb_pierce_upper_return") == 1
    pierce_lower = latest.get("bb_pierce_lower_return") == 1
    walking_upper = latest.get("bb_walking_upper") == 1
    walking_lower = latest.get("bb_walking_lower") == 1
    is_squeeze = latest.get("bb_squeeze") == 1

    if close is None:
        return {"status": "unknown", "summary": "价格数据缺失"}

    # 位置判定
    if boll_up and close >= boll_up:
        position = "触及/突破上轨"
        position_label = "upper"
    elif boll_down and close <= boll_down:
        position = "触及/跌破下轨"
        position_label = "lower"
    elif boll_mid and close > boll_mid:
        position = "中轨上方"
        position_label = "above_mid"
    else:
        position = "中轨下方"
        position_label = "below_mid"

    # 形态
    patterns = []
    if touch_upper:
        patterns.append("触上轨")
    if touch_lower:
        patterns.append("触下轨")
    if pierce_upper:
        patterns.append("穿刺上轨后回归（强回归信号）")
    if pierce_lower:
        patterns.append("穿刺下轨后回归（强回归信号）")
    if walking_upper:
        patterns.append("沿上轨爬行（强趋势，勿逆势做空）")
    if walking_lower:
        patterns.append("沿下轨爬行（强趋势，勿逆势做多）")
    if is_squeeze:
        patterns.append("Squeeze收缩（蓄势待突破）")

    # 带宽状态
    if bw is not None:
        if is_squeeze:
            bw_note = f"带宽{bw:.2f}%处于历史低位（Squeeze），暴风雨前的宁静"
        elif bw < 5:
            bw_note = f"带宽{bw:.2f}%，偏窄"
        elif bw < 10:
            bw_note = f"带宽{bw:.2f}%，适中"
        else:
            bw_note = f"带宽{bw:.2f}%，偏宽（高波动）"
    else:
        bw_note = "N/A"

    # 中轨斜率
    slope_detail = "N/A"
    if boll_mid is not None and len(df) > 5:
        prev_mid = _safe_float(df["ma_mid"].iloc[-6])
        if prev_mid and prev_mid > 0:
            slope = (boll_mid - prev_mid) / prev_mid * 100
            if abs(slope) < 0.5:
                slope_detail = f"中轨走平 ({slope:+.2f}%) — 适宜区间交易"
            elif slope > 0:
                slope_detail = f"中轨向上 ({slope:+.2f}%) — 上升趋势，只做多"
            else:
                slope_detail = f"中轨向下 ({slope:+.2f}%) — 下降趋势，只做空"

    return {
        "status": position_label,
        "status_label": position,
        "close": round(close, 2),
        "boll_up": round(boll_up, 2) if boll_up else None,
        "boll_mid": round(boll_mid, 2) if boll_mid else None,
        "boll_down": round(boll_down, 2) if boll_down else None,
        "bandwidth": round(bw, 3) if bw else None,
        "bandwidth_note": bw_note,
        "slope_detail": slope_detail,
        "patterns": patterns,
        "is_squeeze": is_squeeze,
        "summary": f"价格在{position}，{bw_note}",
        "detail": f"收盘{close:.2f}，布林带 上{boll_up:.2f}/中{boll_mid:.2f}/下{boll_down:.2f}。{bw_note}。{slope_detail}。" + (" ".join(patterns) if patterns else ""),
        "checklist": [
            "中轨方向符合交易方向" + (" ✓" if "向上" in slope_detail or "走平" in slope_detail else " ⚠"),
            "无趋势逆势信号" + (" ✓" if not ((touch_upper and "向上" in slope_detail) or (touch_lower and "向下" in slope_detail)) else " ⚠ 趋势中勿逆势触轨交易"),
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 5. ATR 维度解读
# ═══════════════════════════════════════════════════════════════

def _interpret_atr(df: pd.DataFrame, latest: pd.Series) -> dict:
    atr_val = _safe_float(latest.get("atr"))
    close = _safe_float(latest.get("close"))

    if atr_val is None or close is None:
        return {"status": "unknown", "summary": "ATR数据缺失"}

    # ATR 相对价格的百分比
    atr_pct = round(atr_val / close * 100, 2)

    # ATR 趋势
    atr_trend = "稳定"
    if len(df) > 5:
        prev_atr = _safe_float(df["atr"].iloc[-6])
        if prev_atr and prev_atr > 0:
            chg = atr_val / prev_atr
            if chg > 1.5:
                atr_trend = "异常跳升（变盘预警）"
            elif chg > 1.2:
                atr_trend = "扩张中"
            elif chg < 0.85:
                atr_trend = "收缩中"

    # 波动率水平
    if atr_pct > 5:
        vol_level = "极高波动"
    elif atr_pct > 3:
        vol_level = "高波动"
    elif atr_pct > 1.5:
        vol_level = "中等波动"
    else:
        vol_level = "低波动"

    # 动态止损
    env = str(latest.get("environment", "unknown"))
    multiplier = 2.0 if env == "trend" else 1.5
    stop_distance = round(multiplier * atr_val, 2)
    is_buy = latest.get("buy_signal") == 1

    if is_buy:
        stop_price = round(close - stop_distance, 2)
        stop_note = f"做多止损建议: {stop_price:.2f} (入场价{close:.2f} - {multiplier}×ATR({atr_val:.2f}) = {stop_distance:.2f})"
    elif latest.get("sell_signal") == 1:
        stop_price = round(close + stop_distance, 2)
        stop_note = f"做空止损建议: {stop_price:.2f} (入场价{close:.2f} + {multiplier}×ATR({atr_val:.2f}) = {stop_distance:.2f})"
    else:
        stop_price = None
        stop_note = "无活跃信号，无需设置止损"

    return {
        "status": vol_level,
        "status_label": vol_level,
        "value": round(atr_val, 2),
        "pct": atr_pct,
        "trend": atr_trend,
        "stop_multiplier": multiplier,
        "stop_distance": stop_distance,
        "stop_price": stop_price,
        "stop_note": stop_note,
        "summary": f"ATR {atr_val:.2f} ({atr_pct}%收盘价)，{vol_level}",
        "detail": f"ATR={atr_val:.2f}，占收盘价{atr_pct}%，波动率{atr_trend}。{stop_note}",
        "checklist": [
            "止损距离合理" + (" ✓" if stop_distance is not None and stop_distance < close * 0.1 else " ⚠ 止损距离偏大"),
            "波动率未异常跳升" + (" ✓" if atr_trend != "异常跳升（变盘预警）" else " ⚠ ATR异常跳升，谨慎入场"),
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 6. 出场条件解读
# ═══════════════════════════════════════════════════════════════

def _interpret_exit_triggers(df: pd.DataFrame, latest: pd.Series) -> dict:
    triggers = []
    trigger_labels = {
        "exit_trigger_1": "价格回归中轨（震荡出场）",
        "exit_trigger_2": "KDJ交叉反转（短线出场）",
        "exit_trigger_3": "J值从超买区回落（动量衰竭）",
        "exit_trigger_4": "ATR异常跳升（变盘预警）",
        "exit_trigger_5": "价格跌破MA20（趋势辅助出场）",
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


# ═══════════════════════════════════════════════════════════════
# 7. 交易建议
# ═══════════════════════════════════════════════════════════════

def _interpret_trading_advice(df: pd.DataFrame, latest: pd.Series,
                               base_grade: str, grade: str, env: str) -> dict:
    is_buy = latest.get("buy_signal") == 1
    close = _safe_float(latest.get("close"))
    atr_val = _safe_float(latest.get("atr"))
    kdj_j = _safe_float(latest.get("kdj_j"))
    has_filter = "_weekly_against" in grade

    env_mode_map = {
        "range": "震荡区间交易",
        "trend": "趋势顺势交易",
        "squeeze": "蓄势突破交易",
    }
    mode = env_mode_map.get(env, "等待环境确认")

    if is_buy:
        if base_grade == "S" and not has_filter:
            entry_advice = f"高确信做多信号（{mode}），可重仓入场。止损设在{round(close - 2*atr_val, 2):.2f}（2×ATR）或布林下轨下方"
        elif base_grade == "A" and not has_filter:
            entry_advice = f"标准做多信号（{mode}），可正常仓位入场。确认震荡环境+ATR稳定后执行"
        elif base_grade == "B" or has_filter:
            entry_advice = "试探性做多信号，建议轻仓。等待ATR确认和中轨走平确认后再加仓"
        else:
            entry_advice = "仅观察信号，不推荐入场。等待KDJ金叉配合触下轨确认升级"
    else:
        if base_grade == "S" and not has_filter:
            entry_advice = f"高确信做空信号（{mode}），可重仓入场。止损设在{round(close + 2*atr_val, 2):.2f}（2×ATR）或布林上轨上方"
        elif base_grade == "A" and not has_filter:
            entry_advice = f"标准做空信号（{mode}），可正常仓位入场"
        elif base_grade == "B" or has_filter:
            entry_advice = "试探性做空信号，建议轻仓或等信号升级"
        else:
            entry_advice = "仅观察信号，不推荐入场做空"

    # 出场建议
    exit_count = sum(1 for col in [f"exit_trigger_{i}" for i in range(1, 6)]
                     if latest.get(col, 0) == 1)
    if exit_count > 0:
        exit_advice = f"已有{exit_count}个出场条件触发，建议减仓或平仓"
    else:
        exit_advice = "持仓观察，移动止损至盈亏平衡点"

    # KDJ 趋势钝化警告
    kdj_warning = ""
    if is_buy and kdj_j is not None and kdj_j > 100 and env == "trend":
        kdj_warning = "KDJ在趋势中钝化(J>100)，不要据此逆势做空，顺势持多"
    elif not is_buy and kdj_j is not None and kdj_j < 0 and env == "trend":
        kdj_warning = "KDJ在趋势中钝化(J<0)，不要据此逆势做多，顺势持空"

    # 环境特定建议
    env_advice = ""
    if env == "range":
        env_advice = "目标：布林带中轨（平仓50%），剩余用移动止损跟踪到对面轨道"
    elif env == "trend":
        env_advice = "目标：前高/前低或对面轨道，回调缩量确认后加仓"
    elif env == "squeeze":
        env_advice = "目标：突破方向的对面轨道（Squeeze突破通常幅度较大），止损用2×ATR"

    return {
        "entry_ready": base_grade in ("S", "A") and not has_filter,
        "entry_advice": entry_advice,
        "exit_ready": exit_count > 0,
        "exit_advice": exit_advice,
        "env_advice": env_advice,
        "kdj_warning": kdj_warning,
        "stop_loss_suggestion": f"建议ATR动态止损：震荡1.5×ATR，趋势2×ATR",
        "mode": mode,
        "summary": entry_advice,
        "detail": f"{entry_advice}。{exit_advice}。{env_advice}{'。' + kdj_warning if kdj_warning else ''}",
        "checklist": [
            "入场条件满足" + (" ✓" if base_grade in ("S", "A") and not has_filter else " ○"),
            "交易模式匹配环境" + " ✓",
            "周线方向过滤通过" + (" ✓" if not has_filter else " ⚠"),
            "KDJ未趋势钝化" + (" ✓" if not kdj_warning else " ⚠"),
            "出场条件未触发" + (" ✓" if exit_count == 0 else " ⚠"),
        ],
    }
