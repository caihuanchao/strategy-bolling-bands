"""
双均线交叉策略结构化解读模块。

基于双均线交叉策略指南，为个股生成交叉信号、趋势判定、信号可靠性、
成交量确认、操作建议五个维度的中文解读。
"""

import pandas as pd
import numpy as np


def interpret_dual_ma_all(df: pd.DataFrame) -> dict:
    """
    为双均线策略生成完整结构化解读。

    Args:
        df: DataFrame，需包含 ema_fast, ema_slow, close, volume_ratio,
            buy_signal, sell_signal 列

    Returns:
        {"cross_signal": {...}, "trend": {...}, "reliability": {...},
         "volume": {...}, "trading_advice": {...}}
        每个子 dict 包含 summary, detail, checklist 及指标专属字段
    """
    required = ["ema_fast", "ema_slow"]
    if not all(c in df.columns for c in required):
        return {"error": "数据不足：缺少 EMA 快线/慢线列"}

    latest = df.iloc[-1]
    if pd.isna(latest.get("ema_fast")) or pd.isna(latest.get("ema_slow")):
        return {"error": "数据不足：最新 EMA 值为空"}

    cross = _interpret_cross(df)
    trend = _interpret_trend(df)
    reliability = _interpret_reliability(df, cross, trend)
    volume = _interpret_volume(df)
    trading_advice = _trading_advice(cross, trend, reliability, volume)

    return {
        "cross_signal": cross,
        "trend": trend,
        "reliability": reliability,
        "volume": volume,
        "trading_advice": trading_advice,
    }


# ── 交叉信号 ──────────────────────────────────────────────────────────────

def _interpret_cross(df: pd.DataFrame) -> dict:
    """判断当前金叉/死叉状态及最近一次交叉"""
    ema_fast = df["ema_fast"].values
    ema_slow = df["ema_slow"].values

    if len(ema_fast) < 2:
        return {"status": "data_insufficient", "summary": "数据不足，无法判定交叉状态"}

    cur_fast = float(ema_fast[-1])
    cur_slow = float(ema_slow[-1])
    prev_fast = float(ema_fast[-2])
    prev_slow = float(ema_slow[-2])

    result = {
        "fast_value": round(cur_fast, 2),
        "slow_value": round(cur_slow, 2),
    }

    # 检测最近一次交叉
    cross_detected = None
    cross_idx = -1
    for i in range(len(ema_fast) - 1, 0, -1):
        f_cur, s_cur = float(ema_fast[i]), float(ema_slow[i])
        f_prev, s_prev = float(ema_fast[i - 1]), float(ema_slow[i - 1])
        if pd.isna(f_cur) or pd.isna(s_cur) or pd.isna(f_prev) or pd.isna(s_prev):
            continue
        if f_prev <= s_prev and f_cur > s_cur:
            cross_detected = "golden"
            cross_idx = i
            break
        if f_prev >= s_prev and f_cur < s_cur:
            cross_detected = "death"
            cross_idx = i
            break

    # 当前均线关系
    if cur_fast > cur_slow:
        result["status"] = "golden_cross"
        result["status_label"] = "金叉区域"
        result["detail"] = (
            f"快线 EMA({result['fast_value']}) > 慢线 EMA({result['slow_value']})："
            "当前处于金叉状态，短期均线在长期均线上方运行，多方占优。"
            "快线在慢线之上，意味着近期买入力量强于卖出力量，趋势偏向上涨。"
        )
    elif cur_fast < cur_slow:
        result["status"] = "death_cross"
        result["status_label"] = "死叉区域"
        result["detail"] = (
            f"快线 EMA({result['fast_value']}) < 慢线 EMA({result['slow_value']})："
            "当前处于死叉状态，短期均线在长期均线下方运行，空方占优。"
            "快线在慢线之下，意味着近期卖出力量强于买入力量，趋势偏向下跌。"
        )
    else:
        result["status"] = "neutral"
        result["status_label"] = "均线粘合"
        result["detail"] = "快线与慢线基本持平，均线粘合状态，方向不明，等待选择方向。"

    # 最近交叉信息
    days_since = len(ema_fast) - 1 - cross_idx if cross_idx >= 0 else None
    if cross_detected == "golden":
        result["last_cross"] = "golden"
        result["last_cross_label"] = "最近一次：金叉"
        if days_since is not None:
            result["detail"] += (
                f" 最近一次金叉出现在 {days_since} 个周期前，"
                "之后快线持续在慢线上方运行。"
            )
    elif cross_detected == "death":
        result["last_cross"] = "death"
        result["last_cross_label"] = "最近一次：死叉"
        if days_since is not None:
            result["detail"] += (
                f" 最近一次死叉出现在 {days_since} 个周期前，"
                "之后快线持续在慢线下方运行。"
            )
    else:
        result["last_cross"] = "none"
        result["last_cross_label"] = "近期无交叉"

    result["summary"] = _cross_summary(result)
    result["checklist"] = _cross_checklist(result)
    return result


def _cross_summary(r: dict) -> str:
    status = r.get("status", "")
    if status == "golden_cross":
        return "当前处于金叉区域，快线在慢线上方，多方主导，关注趋势能否持续。"
    if status == "death_cross":
        return "当前处于死叉区域，快线在慢线下方，空方主导，等待反转信号。"
    return "均线粘合，方向不明，宜观望等待方向选择。"


def _cross_checklist(r: dict) -> list:
    status = r.get("status", "")
    items = []
    if status == "golden_cross":
        items.append("金叉确认：不宜追高，等待回踩慢线获得支撑后入场更安全")
        items.append("关注快线斜率：若斜率放缓，金叉动能可能衰减")
    elif status == "death_cross":
        items.append("死叉确认：不宜抄底，等待金叉信号出现后再考虑入场")
        items.append("关注慢线斜率：若慢线也开始向下拐头，下跌趋势可能加速")
    else:
        items.append("均线粘合：保持观望，不预判方向，等均线拉开后再顺势操作")
    return items


# ── 趋势判定 ──────────────────────────────────────────────────────────────

def _interpret_trend(df: pd.DataFrame) -> dict:
    """分析均线方向、多头/空头排列、价格位置"""
    ema_fast = df["ema_fast"].values
    ema_slow = df["ema_slow"].values
    close_arr = df["close"].values

    cur_fast = float(ema_fast[-1])
    cur_slow = float(ema_slow[-1])
    cur_close = float(close_arr[-1])

    result = {
        "fast_value": round(cur_fast, 2),
        "slow_value": round(cur_slow, 2),
        "close": round(cur_close, 2),
    }

    # 斜率方向（用近5周期变化判断）
    lookback = min(5, len(ema_fast) - 1)
    if lookback >= 1:
        fast_prev = float(ema_fast[-1 - lookback])
        slow_prev = float(ema_slow[-1 - lookback])
        fast_slope = (cur_fast - fast_prev) / lookback if lookback > 0 else 0
        slow_slope = (cur_slow - slow_prev) / lookback if lookback > 0 else 0
        result["fast_slope"] = round(fast_slope, 4)
        result["slow_slope"] = round(slow_slope, 4)

        fast_dir = "向上" if fast_slope > 0.001 else "向下" if fast_slope < -0.001 else "走平"
        slow_dir = "向上" if slow_slope > 0.001 else "向下" if slow_slope < -0.001 else "走平"
    else:
        result["fast_slope"] = 0
        result["slow_slope"] = 0
        fast_dir = "数据不足"
        slow_dir = "数据不足"

    result["fast_direction"] = fast_dir
    result["slow_direction"] = slow_dir

    # 多头/空头排列判断
    if cur_close > cur_fast > cur_slow:
        result["alignment"] = "bullish"
        result["alignment_label"] = "多头排列"
        result["detail"] = (
            f"价格({cur_close:.2f}) > 快线({cur_fast:.2f}) > 慢线({cur_slow:.2f})："
            "标准多头排列。价格在两条均线上方运行，快线在慢线上方，"
            "均线方向共同向上时是理想的做多环境。"
        )
    elif cur_close < cur_fast < cur_slow:
        result["alignment"] = "bearish"
        result["alignment_label"] = "空头排列"
        result["detail"] = (
            f"价格({cur_close:.2f}) < 快线({cur_fast:.2f}) < 慢线({cur_slow:.2f})："
            "标准空头排列。价格在两条均线下方运行，快线在慢线下方，"
            "均线方向共同向下时是理想的做空/观望环境。"
        )
    elif cur_fast > cur_slow and cur_close < cur_fast:
        result["alignment"] = "mixed_bullish"
        result["alignment_label"] = "均线多头但价格回撤"
        result["detail"] = (
            f"快线({cur_fast:.2f}) > 慢线({cur_slow:.2f})，但价格({cur_close:.2f})回落到快线下方。"
            "均线仍保持多头排列，但价格短期回撤。若回踩慢线获得支撑，是不错的入场点。"
        )
    elif cur_fast < cur_slow and cur_close > cur_fast:
        result["alignment"] = "mixed_bearish"
        result["alignment_label"] = "均线空头但价格反弹"
        result["detail"] = (
            f"快线({cur_fast:.2f}) < 慢线({cur_slow:.2f})，但价格({cur_close:.2f})反弹至快线上方。"
            "均线仍保持空头排列，价格短期反弹。关注反弹能否持续突破慢线。"
        )
    else:
        result["alignment"] = "mixed"
        result["alignment_label"] = "排列混乱"
        result["detail"] = "价格与均线关系不明确，趋势方向不清，建议观望。"

    # 均线方向补充
    result["detail"] += (
        f" 快线方向：{fast_dir}，慢线方向：{slow_dir}。"
        + (
            "两条均线同向向上，趋势共振偏多。"
            if fast_dir == "向上" and slow_dir == "向上"
            else "两条均线同向向下，趋势共振偏空。"
            if fast_dir == "向下" and slow_dir == "向下"
            else "均线方向不一致，趋势存在分歧。"
        )
    )

    result["summary"] = _trend_summary(result)
    result["checklist"] = _trend_checklist(result)
    return result


def _trend_summary(r: dict) -> str:
    alignment = r.get("alignment", "")
    if alignment == "bullish":
        return "多头排列，价格在均线上方运行，趋势健康，适合顺势做多。"
    if alignment == "bearish":
        return "空头排列，价格在均线下方运行，趋势偏空，以观望或做空为主。"
    if alignment == "mixed_bullish":
        return "均线仍多头但价格回撤，关注慢线支撑力度，企稳可考虑入场。"
    if alignment == "mixed_bearish":
        return "均线仍空头但价格反弹，关注反弹持续性，不宜追涨。"
    return "趋势不明朗，等待均线关系清晰后再做决策。"


def _trend_checklist(r: dict) -> list:
    alignment = r.get("alignment", "")
    items = []
    if alignment == "bullish":
        items.append("多头排列：顺势持有，可沿快线移动止损保护利润")
        items.append("若价格回踩慢线获得支撑，是加仓/入场时机")
    elif alignment == "bearish":
        items.append("空头排列：不逆势做多，等待金叉信号出现")
        items.append("若持有空头仓位，可沿快线移动止损")
    elif alignment == "mixed_bullish":
        items.append("多头趋势中的回撤：观察慢线能否有效支撑")
        items.append("若放量跌破慢线，多头趋势可能转弱，考虑减仓")
    elif alignment == "mixed_bearish":
        items.append("空头趋势中的反弹：观察慢线能否被有效突破")
        items.append("若放量站上慢线，空头趋势可能转多，关注金叉确认")
    else:
        items.append("趋势不明：以观望为主，降低仓位等待方向明确")
    return items


# ── 信号可靠性 ──────────────────────────────────────────────────────────────

def _interpret_reliability(df: pd.DataFrame, cross: dict, trend: dict) -> dict:
    """按指南分级体系评估信号可靠性（弱势/标准/强势/金叉死叉）"""
    result = {}

    fast_val = cross.get("fast_value")
    slow_val = cross.get("slow_value")
    if fast_val is None or slow_val is None:
        return {"level": "unknown", "stars": "☆☆☆☆☆", "summary": "无法评估"}

    has_cross = cross.get("last_cross") in ("golden", "death")
    trend_confirmed = _trend_direction_confirmed(cross, trend)
    price_ok = _price_position_confirmed(cross, trend)
    volume_ok = _volume_confirmed(df)

    conditions_met = []
    conditions_missing = []

    if has_cross:
        conditions_met.append("✓ 快慢线交叉完成")
    else:
        conditions_missing.append("✗ 近期无明确交叉信号")

    if trend_confirmed:
        conditions_met.append("✓ 均线方向与交叉方向一致")
    else:
        conditions_missing.append("✗ 均线方向不配合")

    if price_ok:
        conditions_met.append("✓ 价格位置配合信号方向")
    else:
        conditions_missing.append("✗ 价格位置不理想")

    if volume_ok:
        conditions_met.append("✓ 成交量放大配合")
    else:
        conditions_missing.append("✗ 成交量未有效放大")

    # 分级判定
    conditions_count = len(conditions_met)
    if conditions_count >= 4:
        result["level"] = "strong"
        result["stars"] = "★★★★☆"
        result["level_label"] = "强势信号"
        result["detail"] = (
            "当前满足全部4项确认条件：交叉完成、均线方向一致、价格位置配合、成交量放大。"
            "信号可靠性较高，属于指南中的强势信号级别，可重点关注操作机会。"
        )
    elif conditions_count == 3:
        result["level"] = "standard"
        result["stars"] = "★★★☆☆"
        result["level_label"] = "标准信号"
        result["detail"] = (
            "当前满足3项确认条件，属于标准信号级别。信号有一定可靠性，"
            "但缺乏全部共振确认，操作时需控制仓位，设好止损。"
        )
    elif conditions_count == 2:
        result["level"] = "weak"
        result["stars"] = "★★☆☆☆"
        result["level_label"] = "弱势信号"
        result["detail"] = (
            "仅满足2项确认条件，信号较弱。震荡市中此类信号容易出现假突破，"
            "建议等待更多条件确认后再操作，或仅以极小仓位试探。"
        )
    else:
        result["level"] = "no_signal"
        result["stars"] = "★☆☆☆☆"
        result["level_label"] = "无有效信号"
        result["detail"] = (
            "当前信号确认条件不足，不具备操作价值。建议继续观望，"
            "等待明确的交叉信号及均线方向确认后再考虑入场。"
        )

    result["conditions_met"] = conditions_met
    result["conditions_missing"] = conditions_missing

    result["summary"] = (
        f"信号可靠性：{result['level_label']} ({result['stars']})。"
        f"满足 {conditions_count}/4 项确认条件。"
    )
    result["checklist"] = _reliability_checklist(result)
    return result


def _trend_direction_confirmed(cross: dict, trend: dict) -> bool:
    """检查均线方向是否与交叉方向一致"""
    status = cross.get("status", "")
    fast_dir = trend.get("fast_direction", "")
    slow_dir = trend.get("slow_direction", "")
    if status == "golden_cross":
        return fast_dir in ("向上", "走平") and slow_dir in ("向上", "走平")
    if status == "death_cross":
        return fast_dir in ("向下", "走平") and slow_dir in ("向下", "走平")
    return False


def _price_position_confirmed(cross: dict, trend: dict) -> bool:
    """检查价格位置是否配合信号方向"""
    alignment = trend.get("alignment", "")
    status = cross.get("status", "")
    if status == "golden_cross":
        return alignment in ("bullish", "mixed_bullish")
    if status == "death_cross":
        return alignment in ("bearish", "mixed_bearish")
    return False


def _volume_confirmed(df: pd.DataFrame) -> bool:
    """检查成交量是否有效放大"""
    if "volume_ratio" not in df.columns:
        return False
    latest_vr = df["volume_ratio"].iloc[-1]
    if pd.isna(latest_vr):
        return False
    return float(latest_vr) >= 1.2


def _reliability_checklist(r: dict) -> list:
    items = []
    level = r.get("level", "")
    if level == "strong":
        items.append("强势信号：可正常仓位操作，但仍需设好止损")
        items.append("关注信号持续性：若条件逐日减少，提防信号衰减")
    elif level == "standard":
        items.append("标准信号：半仓操作，严格止损")
        items.append("等待缺失条件补足后可加仓")
    elif level == "weak":
        items.append("弱势信号：仅轻仓试探或不参与")
        items.append("震荡市中假信号多，建议等待更强信号")
    else:
        items.append("无有效信号：保持观望，等待条件成熟")
    return items


# ── 成交量分析 ──────────────────────────────────────────────────────────────

def _interpret_volume(df: pd.DataFrame) -> dict:
    """成交量配合分析"""
    result = {}

    if "volume_ratio" not in df.columns:
        return {"is_confirmed": False, "summary": "成交量数据不足，无法分析"}

    latest_vr = df["volume_ratio"].iloc[-1]
    if pd.isna(latest_vr):
        return {"is_confirmed": False, "summary": "成交量数据缺失"}

    vr = float(latest_vr)
    result["volume_ratio"] = round(vr, 2)

    if vr >= 2.0:
        result["is_confirmed"] = True
        result["level"] = "strong"
        result["level_label"] = "显著放量"
        result["detail"] = (
            f"量比 {vr:.1f}x（≥2.0）：成交量显著放大，为均值的2倍以上。"
            "放量配合交叉信号，可靠性大幅提升，说明市场资金积极参与方向选择。"
        )
    elif vr >= 1.5:
        result["is_confirmed"] = True
        result["level"] = "moderate"
        result["level_label"] = "温和放量"
        result["detail"] = (
            f"量比 {vr:.1f}x（1.5-2.0）：成交量温和放大，对信号有一定确认作用。"
            "放量程度适中，信号可靠性中等。"
        )
    elif vr >= 1.2:
        result["is_confirmed"] = True
        result["level"] = "mild"
        result["level_label"] = "轻微放量"
        result["detail"] = (
            f"量比 {vr:.1f}x（1.2-1.5）：成交量略有放大，勉强达到确认阈值。"
            "放量不够显著，信号确认力度偏弱。"
        )
    else:
        result["is_confirmed"] = False
        result["level"] = "insufficient"
        result["level_label"] = "缩量"
        result["detail"] = (
            f"量比 {vr:.1f}x（<1.2）：成交量未有效放大。"
            "缩量交叉往往是假信号，尤其在震荡市中容易被反复打脸。"
            "建议等待放量确认后再行动。"
        )

    # 成交量趋势（近5周期均值 vs 近20周期均值）
    if len(df) >= 20 and "volume" in df.columns:
        vol = df["volume"].values
        recent_avg = np.mean(vol[-5:])
        mid_avg = np.mean(vol[-20:])
        if recent_avg > mid_avg * 1.1:
            result["volume_trend"] = "放量趋势"
            result["detail"] += " 近5日成交量均值高于20日均值，资金参与度上升。"
        elif recent_avg < mid_avg * 0.9:
            result["volume_trend"] = "缩量趋势"
            result["detail"] += " 近5日成交量均值低于20日均值，市场参与度下降。"
        else:
            result["volume_trend"] = "量能平稳"

    result["summary"] = (
        f"成交量：{result.get('level_label', '未知')}（量比 {vr:.1f}x），"
        + ("放量确认信号有效。" if result["is_confirmed"] else "缩量信号可靠性较低。")
    )
    result["checklist"] = _volume_checklist(result)
    return result


def _volume_checklist(r: dict) -> list:
    items = []
    is_confirmed = r.get("is_confirmed", False)
    if is_confirmed:
        items.append("放量配合：信号有效性提升，可按计划操作")
        items.append("关注后续量能持续性，若量能递减提防信号衰减")
    else:
        items.append("缩量信号：谨慎对待，不宜重仓参与")
        items.append("等待放量确认后再行动，缩量交叉常为假突破")
    return items


# ── 操作建议 ──────────────────────────────────────────────────────────────

def _trading_advice(cross: dict, trend: dict, reliability: dict, volume: dict) -> dict:
    """综合生成操作建议清单"""
    result = {}

    status = cross.get("status", "")
    level = reliability.get("level", "")
    alignment = trend.get("alignment", "")
    vol_ok = volume.get("is_confirmed", False)

    # 入场建议
    if status == "golden_cross" and level in ("strong", "standard"):
        result["entry_ready"] = True
        result["entry_advice"] = (
            "当前金叉信号配合趋势确认，满足入场条件。"
            + ("但建议等待回踩慢线后再入场，获得更优价格和更近止损位。" if alignment == "mixed_bullish" else "")
        )
    elif status == "death_cross" and level in ("strong", "standard"):
        result["entry_ready"] = False
        result["entry_advice"] = "当前为死叉信号且可靠性较高，不宜做多。可关注做空机会或继续观望。"
    else:
        result["entry_ready"] = False
        result["entry_advice"] = "当前信号条件不充分，建议继续观望，等待更强的金叉信号。"

    # 出场建议
    if status == "death_cross":
        result["exit_ready"] = True
        result["exit_advice"] = "死叉已出现，若持有多头仓位应考虑减仓或平仓。跟踪止损可沿慢线移动。"
    elif alignment == "bearish":
        result["exit_ready"] = True
        result["exit_advice"] = "空头排列中，多头仓位风险加大。若快线拐头向下且价格跌破慢线，应果断离场。"
    else:
        result["exit_ready"] = False
        result["exit_advice"] = "暂无明确出场信号，持仓者可继续持有，但需设好移动止损。"

    # 止损建议
    slow_val = cross.get("slow_value")
    if slow_val:
        result["stop_loss_suggestion"] = (
            f"建议止损位设在慢线 EMA 下方 2-3%（约 ¥{slow_val * 0.97:.2f}）"
            "或近期低点下方。沿慢线移动止损可保护利润。"
        )
    else:
        result["stop_loss_suggestion"] = "数据不足，无法给出具体止损建议。建议回看近期低点设止损。"

    result["summary"] = result.get("entry_advice", "观望为主")
    result["checklist"] = _advice_checklist(result, cross, reliability, vol_ok)
    return result


def _advice_checklist(result: dict, cross: dict, reliability: dict, vol_ok: bool) -> list:
    items = []
    if result.get("entry_ready"):
        items.append("入场前：等待一根K线收盘价确认，避免盘中假突破")
        items.append("仓位管理：每笔风险不超过总账户 2%，计算好止损距离")
        items.append("入场后：沿慢线移动止损，保护利润")
    else:
        items.append("观望：等待信号条件改善，不急于入场")

    if result.get("exit_ready"):
        items.append("考虑减仓或设置更紧的止损保护已有利润")

    if cross.get("status") == "golden_cross" and cross.get("last_cross") == "golden":
        # 检查交叉是否很久之前（动能可能衰减）
        items.append("金叉后若快线斜率放缓，提防动能衰减，可适当减仓")

    if not vol_ok:
        items.append("成交量不足：即使信号出现也不宜重仓，等待放量确认")

    items.append("双均线策略在震荡市中假信号多，如有疑虑可结合 ADX 等指标做趋势过滤")
    return items
