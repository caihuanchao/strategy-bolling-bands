"""
技术指标结构化解读模块。

接收已清洗的浮点数值（None 表示缺失），返回中文解读 dict。
参考案例：docs/技术指标解读案例
"""

def interpret_all(latest, prev=None):
    """
    为所有指标生成结构化解读。

    Args:
        latest: dict with keys close, macd, macd_signal, macd_histogram, rsi, boll_up, boll_mid, boll_down
        prev: dict with same keys (previous period), optional

    Returns:
        {"macd": {...}, "rsi": {...}, "bollinger": {...}}
    """
    if prev is None:
        prev = {}
    result = {}
    result["macd"] = interpret_macd(latest, prev)
    result["rsi"] = interpret_rsi(latest, prev)
    result["bollinger"] = interpret_bollinger(latest, prev)
    return result


# ── MACD ──────────────────────────────────────────────────────────────

def interpret_macd(latest, prev=None):
    """生成 MACD 指标结构化解读。"""
    if prev is None:
        prev = {}

    dif = latest.get("macd")
    dea = latest.get("macd_signal")
    bar = latest.get("macd_histogram")

    prev_dif = prev.get("macd")
    prev_dea = prev.get("macd_signal")
    prev_bar = prev.get("macd_histogram")

    # All missing → minimal
    if dif is None and dea is None and bar is None:
        return {"dif": None, "dea": None, "bar": None}

    # Compute bar if derivable
    if bar is None and dif is not None and dea is not None:
        bar = dif - dea

    result = {
        "dif": dif,
        "dea": dea,
        "bar": bar,
    }

    # ── 1. 整体位置 ──
    if dif is not None and dea is not None:
        if dif > 0 and dea > 0:
            result["position_label"] = "零轴上方"
            result["position_detail"] = (
                "DIF、DEA 均在 0 轴以上：短期均线 > 长期均线，"
                "整体处于多头主导的上涨趋势。"
            )
        elif dif < 0 and dea < 0:
            result["position_label"] = "零轴下方"
            result["position_detail"] = (
                "DIF、DEA 均在 0 轴以下：短期均线 < 长期均线，"
                "整体处于空头主导的下跌趋势。"
            )
        else:
            result["position_label"] = "零轴附近"
            result["position_detail"] = (
                "DIF、DEA 在 0 轴附近：多空力量均衡，处于方向选择期。"
            )
    else:
        result["position_label"] = "数据不足"
        result["position_detail"] = ""

    # ── 2. 快慢线关系 ──
    if dif is not None and dea is not None:
        spread = abs(dif - dea)
        threshold = 0.05 * max(abs(dif), abs(dea), 1)

        if spread <= threshold:
            result["cross_label"] = "粘合"
            result["cross_detail"] = (
                "DIF 与 DEA 非常接近，快慢线粘合：趋势方向不明，"
                "即将选择方向，需密切关注后续发散。"
            )
        elif dif > dea:
            if prev_dif is not None and prev_dea is not None and prev_dif <= prev_dea:
                result["cross_label"] = "刚金叉 ↗"
                result["cross_detail"] = (
                    "DIF 刚上穿 DEA 形成金叉：短期看涨信号，"
                    "若后续红柱放大并站上 0 轴，确认多头趋势。"
                )
            else:
                result["cross_label"] = "金叉 ↗"
                result["cross_detail"] = (
                    "DIF > DEA：金叉状态，多头占优，"
                    "快线在慢线上方运行，趋势偏多。"
                )
        else:
            if prev_dif is not None and prev_dea is not None and prev_dif >= prev_dea:
                result["cross_label"] = "刚死叉 ↘"
                result["cross_detail"] = (
                    "DIF 刚下穿 DEA 形成死叉：短期看跌信号，"
                    "若后续绿柱放大且持续在 0 轴下方，确认空头趋势。"
                )
            else:
                result["cross_label"] = "死叉 ↘"
                result["cross_detail"] = (
                    "DIF < DEA：死叉状态，空头占优，"
                    "快线在慢线下方运行，趋势偏空。"
                )
    else:
        result["cross_label"] = "数据不足"
        result["cross_detail"] = ""

    # ── 3. 动能分析 ──
    if bar is not None:
        abs_bar = abs(bar)
        # Near-zero threshold: tiny momentum
        near_zero = 0.05 * max(abs(dif) if dif else 1, abs(dea) if dea else 1, 1)

        if abs_bar <= near_zero and near_zero < 0.02:
            near_zero = 0.02

        if abs_bar <= near_zero:
            result["momentum_label"] = "动能衰竭"
            result["momentum_detail"] = (
                "MACD 柱接近零轴，多空动能均已衰竭，"
                "市场处于平衡状态，变盘前兆。"
            )
        elif bar > 0:
            if prev_bar is not None and bar > prev_bar:
                result["momentum_label"] = "多方动能增强"
                result["momentum_detail"] = (
                    "MACD 红柱持续放大：多头动能增强，"
                    "短期上涨有延续性，可顺势持有。"
                )
            elif prev_bar is not None and bar < prev_bar:
                result["momentum_label"] = "多方动能减弱"
                result["momentum_detail"] = (
                    "MACD 红柱缩短：多头动能减弱，"
                    "上涨可能接近尾声，关注是否翻绿。"
                )
            else:
                result["momentum_label"] = "多方占优"
                result["momentum_detail"] = (
                    "MACD 红柱：多方主导，红柱越长动能越强。"
                )
        else:
            if prev_bar is not None and bar < prev_bar:
                result["momentum_label"] = "空方动能增强"
                result["momentum_detail"] = (
                    "MACD 绿柱持续放大：空头动能增强，"
                    "短期下跌有延续性，不急于抄底。"
                )
            elif prev_bar is not None and bar > prev_bar:
                result["momentum_label"] = "空方动能减弱"
                result["momentum_detail"] = (
                    "MACD 绿柱缩短：空头动能减弱，"
                    "但绝对值不大，下跌有放缓/磨底迹象。"
                )
            else:
                result["momentum_label"] = "空方占优"
                result["momentum_detail"] = (
                    "MACD 绿柱：空方主导，绿柱越长空方越强。"
                )
    else:
        result["momentum_label"] = ""
        result["momentum_detail"] = ""

    # ── 4. 一句话总结 ──
    result["summary"] = _macd_summary(result)

    # ── 5. 操作清单 ──
    result["checklist"] = _macd_checklist(result)

    return result


def _macd_summary(r):
    """基于各维度状态组合生成一句话总结。"""
    pos = r.get("position_label", "")
    cross = r.get("cross_label", "")
    mom = r.get("momentum_label", "")

    # Below zero + dead cross
    if "零轴下方" in pos and "死叉" in cross:
        if "动能减弱" in mom or "衰竭" in mom:
            return "当前处于明显空头趋势，但短期下跌动能减弱，暂无强势反转信号，偏弱势震荡或筑底。"
        if "动能增强" in mom:
            return "当前处于明显空头趋势，且下跌动能仍在加强，不宜盲目抄底，规避为主。"
        return "当前处于明显空头趋势，死叉运行中，整体偏弱，以观望或轻仓应对。"
    # Below zero + golden cross
    if "零轴下方" in pos and "金叉" in cross:
        return "0 轴下方金叉：空头趋势中的反弹信号，多为反弹而非反转，可短线参与但需快进快出。"
    # Above zero + golden cross
    if "零轴上方" in pos and "金叉" in cross:
        if "动能增强" in mom:
            return "当前处于多头趋势，金叉运行且动能增强，趋势健康，可顺势做多。"
        return "当前处于多头趋势，金叉运行中，整体偏多，持仓者可继续持有。"
    # Above zero + dead cross
    if "零轴上方" in pos and "死叉" in cross:
        return "多头趋势中出现死叉：上涨中的回调信号，趋势尚未反转但需警惕动能变化。"
    # Near zero
    if "零轴附近" in pos:
        if "粘合" in cross:
            return "MACD 在零轴附近粘合，多空力量均衡，处于变盘关键位置，等待方向选择。"
        return "MACD 在零轴附近，方向不明朗，以观望为主。"
    # Generic fallbacks
    if "动能衰竭" in mom:
        return "多空动能均已衰竭，市场进入平衡状态，变盘在即，等待明确信号后操作。"
    if "多方" in mom and "增强" in mom:
        return "多头动能持续增强，短期趋势偏强，可顺势操作。"
    if "空方" in mom and "增强" in mom:
        return "空头动能持续增强，短期趋势偏弱，以规避风险为主。"
    return "MACD 指标信号中性，建议结合其他指标综合判断。"


def _macd_checklist(r):
    """基于 MACD 状态生成操作清单。"""
    items = []
    pos = r.get("position_label", "")
    cross = r.get("cross_label", "")
    mom = r.get("momentum_label", "")

    # 盘面定性
    items.append(_macd_qualitative(pos, cross, mom))

    # 执行纪律
    if "零轴下方" in pos:
        items.append("严禁重仓抄底，不左侧盲买")
        if "金叉" not in cross:
            items.append("不追空、不加空单，空头动能可能已不足")
    if "零轴上方" in pos:
        if "死叉" in cross:
            items.append("多头持仓适当减仓或设好止盈，不急于加仓")

    # 进场/离场条件
    if "零轴下方" in pos:
        items.append("稳健进场条件：DIF 上穿 DEA 金叉 + 绿柱持续缩短翻红 + 价格站稳短期均线")
        items.append("破位规避：DIF/DEA 继续向下张口 + 绿柱明显拉长 → 绝不接盘")
    if "零轴上方" in pos:
        items.append("加仓条件：金叉持续 + 红柱放大 + 价格站稳中轨")
        items.append("减仓信号：DIF 下穿 DEA 死叉 + 红柱持续缩短")

    # 粘合特殊提示
    if "粘合" in cross:
        items.append("粘合期间方向不明，不频繁交易，等待放量突破确认方向")

    # 通用风控
    items.append("试单只做小仓，不一次性满仓")
    items.append("若买入后 MACD 重新恶化（死叉+绿柱放大），无条件止损")
    if "零轴下方" in pos:
        items.append("0 轴下方的金叉多为反弹而非反转，见好就收，不恋战")
    items.append("温馨提示：仅技术指标参考，不构成投资建议，需结合成交量、板块大势一起判断")

    return items


def _macd_qualitative(pos, cross, mom):
    """生成 MACD 盘面定性一句话。"""
    parts = []
    if "零轴上方" in pos:
        parts.append("大趋势多头")
    elif "零轴下方" in pos:
        parts.append("大趋势空头")
    else:
        parts.append("趋势方向不明")

    if "金叉" in cross:
        parts.append("维持金叉")
    elif "死叉" in cross:
        parts.append("维持死叉")
    elif "粘合" in cross:
        parts.append("快慢线粘合")

    if "动能增强" in mom:
        parts.append("动能持续增强")
    elif "动能减弱" in mom:
        parts.append("动能减弱中")
    elif "衰竭" in mom:
        parts.append("动能衰竭，变盘前兆")
    elif "多方" in mom:
        parts.append("多方略占优")
    elif "空方" in mom:
        parts.append("空方略占优")

    return "MACD 盘面定性：" + "，".join(parts)


# ── RSI ───────────────────────────────────────────────────────────────

def interpret_rsi(latest, prev=None):
    """生成 RSI 指标结构化解读。"""
    if prev is None:
        prev = {}

    rsi = latest.get("rsi")
    prev_rsi = prev.get("rsi")

    if rsi is None:
        return {"value": None}

    result = {"value": rsi}

    # 1. 区域判断
    if rsi >= 80:
        result["zone_label"] = "严重超买 ⚠️"
        result["zone_detail"] = (
            "RSI ≥ 80：进入严重超买区域，短期过热风险极高，"
            "市场情绪极度亢奋，大概率出现回调或快速回落。"
        )
    elif rsi >= 70:
        result["zone_label"] = "超买 ⚠️"
        result["zone_detail"] = (
            "RSI 在 70-80 之间：超买区域，短期可能回调，"
            "不宜追高，持仓者可考虑分批止盈。"
        )
    elif rsi >= 50:
        result["zone_label"] = "偏强"
        result["zone_detail"] = (
            "RSI 在 50-70 之间：多方占优，趋势偏强，"
            "50 以上运行说明市场处于多头环境。"
        )
    elif rsi >= 30:
        result["zone_label"] = "偏弱"
        result["zone_detail"] = (
            "RSI 在 30-50 之间：空方占优，趋势偏弱，"
            "50 以下运行说明市场处于空头环境。"
        )
    elif rsi >= 20:
        result["zone_label"] = "超卖 ⚡"
        result["zone_detail"] = (
            "RSI 在 20-30 之间：超卖区域，短期可能出现技术反弹，"
            "关注买入机会，但不急于重仓。"
        )
    else:
        result["zone_label"] = "严重超卖 ⚡"
        result["zone_detail"] = (
            "RSI < 20：进入严重超卖区域，市场极度恐慌，"
            "短期反弹概率较高，但需等待企稳信号。"
        )

    # 2. 趋势方向
    if prev_rsi is not None:
        if rsi > prev_rsi:
            result["trend_label"] = "回升 ↑"
        elif rsi < prev_rsi:
            result["trend_label"] = "回落 ↓"
        else:
            result["trend_label"] = "持平"
    else:
        result["trend_label"] = ""

    # 3. 总结
    result["summary"] = _rsi_summary(result)

    # 4. 操作清单
    result["checklist"] = _rsi_checklist(result)

    return result


def _rsi_summary(r):
    zone = r.get("zone_label", "")
    trend = r.get("trend_label", "")

    if "严重超买" in zone:
        return f"RSI 进入严重超买区域（{r['value']:.1f}），市场极度亢奋，回调风险很大，不宜追高。"
    if "超买" in zone:
        if "回落" in trend:
            return f"RSI 处于超买区域且开始回落（{r['value']:.1f}），超买正在修复，可观察回落至 50 附近的机会。"
        return f"RSI 处于超买区域（{r['value']:.1f}），多方强势但短期过热，注意回调风险。"
    if "偏强" in zone:
        if "回升" in trend:
            return f"RSI 偏强且继续走强（{r['value']:.1f}），多方占优，可顺势操作。"
        return f"RSI 偏强（{r['value']:.1f}），多头环境运行中。"
    if "偏弱" in zone:
        if "回落" in trend:
            return f"RSI 偏弱且继续走弱（{r['value']:.1f}），空方占优，观望为主。"
        return f"RSI 偏弱（{r['value']:.1f}），空头环境运行中。"
    if "超卖" in zone:
        if "回升" in trend:
            return f"RSI 从超卖区域回升（{r['value']:.1f}），有反弹迹象，可关注短线机会。"
        return f"RSI 处于超卖区域（{r['value']:.1f}），短期超跌，关注反弹契机。"
    if "严重超卖" in zone:
        return f"RSI 进入严重超卖区域（{r['value']:.1f}），市场极度恐慌，不宜盲目割肉，等待反弹信号。"

    return f"RSI = {r['value']:.1f}，指标中性。"


def _rsi_checklist(r):
    zone = r.get("zone_label", "")
    trend = r.get("trend_label", "")
    items = []

    if "严重超买" in zone:
        items.append("极端风险区域，不建议新开多单")
        items.append("持多仓者应大幅减仓或清仓止盈")
        items.append("可关注做空机会，但需等 RSI 回落确认")
    elif "超买" in zone:
        items.append("不追高，不新增多头仓位")
        items.append("持有多仓者分批止盈")
        items.append("等待 RSI 回落至 50-60 区间再评估")
    elif "偏强" in zone:
        items.append("多头环境，可顺势持有")
        items.append("新多单在回调至支撑位时轻仓参与")
        items.append("若 RSI 逼近 70 注意减仓")
    elif "偏弱" in zone:
        items.append("空头环境，以观望为主")
        items.append("不急于抄底，等 RSI 企稳或回升信号")
        items.append("持仓者可设止损，不割在地板")
    elif "超卖" in zone:
        items.append("超跌区域，关注反弹机会但控制仓位")
        items.append("等 RSI 回升 + 价格企稳后再试多")
        items.append("不宜盲目杀跌，止损设在关键支撑下方")
    elif "严重超卖" in zone:
        items.append("极端恐慌区域，不盲目割肉")
        items.append("等待 RSI 回升至 30 以上再考虑操作")
        items.append("超跌反弹往往力度较大，但需要有企稳确认")

    return items


# ── Bollinger Bands ────────────────────────────────────────────────────

def interpret_bollinger(latest, prev=None):
    """生成布林带指标结构化解读。"""
    if prev is None:
        prev = {}

    close = latest.get("close")
    boll_up = latest.get("boll_up")
    boll_mid = latest.get("boll_mid")
    boll_down = latest.get("boll_down")

    if close is None or boll_up is None or boll_mid is None or boll_down is None:
        return {"position_label": "数据不足"}

    # 无效布林带
    if boll_up <= boll_down:
        return {"position_label": "数据异常"}

    result = {}

    # 1. 位置判断
    if close >= boll_up:
        result["position_label"] = "上轨附近"
        result["position_detail"] = (
            "价格触及或突破布林带上轨：短期处于强势状态，"
            "但上轨附近通常有压力，回踩概率较大。若放量突破上轨，"
            "则可能是主升浪启动信号。"
        )
    elif close <= boll_down:
        result["position_label"] = "下轨附近"
        result["position_detail"] = (
            "价格触及或跌破布林带下轨：短期处于弱势状态，"
            "但下轨附近通常有支撑，反弹概率较大。若放量跌破下轨，"
            "则可能是主跌浪延续信号。"
        )
    elif close >= boll_mid:
        result["position_label"] = "中上区间"
        result["position_detail"] = (
            "价格位于布林带中上区间：多方占优，价格在中轨上方运行，"
            "趋势偏健康。关注是否能突破上轨打开上涨空间。"
        )
    else:
        result["position_label"] = "中下区间"
        result["position_detail"] = (
            "价格位于布林带中下区间：空方占优，价格在中轨下方运行，"
            "趋势偏弱。关注是否能守住下轨支撑。"
        )

    # 2. %B (归一化位置)
    band_range = boll_up - boll_down
    if band_range > 0:
        percent_b = (close - boll_down) / band_range
        result["percent_b"] = percent_b
        if percent_b > 1.0:
            result["position_detail"] += " %B > 1，价格已突破上轨，短期过热。"
        elif percent_b < 0.0:
            result["position_detail"] += " %B < 0，价格已跌破下轨，短期超跌。"
    else:
        result["percent_b"] = None

    # 3. 带宽分析
    if boll_mid > 0:
        bandwidth = band_range / boll_mid
        result["bandwidth"] = bandwidth
        if bandwidth > 0.4:
            result["bandwidth_label"] = "较宽"
            bandwidth_note = "布林带带宽较宽（>40%）：市场波动剧烈，趋势行情中，适合顺势操作。"
        elif bandwidth < 0.1:
            result["bandwidth_label"] = "较窄（收窄）"
            bandwidth_note = "布林带带宽较窄（<10%）：布林带收窄，市场处于盘整蓄力阶段，即将选择方向变盘。"
        else:
            result["bandwidth_label"] = "正常"
            bandwidth_note = "布林带带宽正常：市场波动适中，趋势运行健康。"
        result["position_detail"] += " " + bandwidth_note
    else:
        result["bandwidth"] = None
        result["bandwidth_label"] = ""

    # 4. 总结
    result["summary"] = _bollinger_summary(result)

    # 5. 操作清单
    result["checklist"] = _bollinger_checklist(result)

    return result


def _bollinger_summary(r):
    pos = r.get("position_label", "")
    bw = r.get("bandwidth_label", "")

    if "上轨附近" in pos:
        return f"价格运行至上轨附近，短期强势但需警惕回调，{'波动较大' if '较宽' in bw else '关注是否能持续强势'}。"
    if "下轨附近" in pos:
        return f"价格运行至下轨附近，短期超跌关注支撑力度，{'波动剧烈' if '较宽' in bw else '可能迎来反弹'}。"
    if "中上区间" in pos:
        return f"价格运行于布林带中上区间，多方占优，{'趋势行情中' if '较宽' in bw else '运行健康'}。"
    if "中下区间" in pos:
        return f"价格运行于布林带中下区间，空方占优，{'需警惕加速下行' if '较宽' in bw else '偏弱震荡'}。"
    return "布林带位置中性。"


def _bollinger_checklist(r):
    pos = r.get("position_label", "")
    bw = r.get("bandwidth_label", "")
    items = []

    if "上轨附近" in pos:
        items.append("价格在上轨附近：不宜追高，持股者可持有但不加仓")
        if "较宽" in bw:
            items.append("带宽较宽+上轨：主升浪可能，设好移动止盈，享受趋势")
        else:
            items.append("若连续多日触及上轨放量，关注突破是否有效")
        items.append("若价格回落跌破中轨，考虑减仓或止盈")

    elif "下轨附近" in pos:
        items.append("价格在下轨附近：不急于抄底，等待企稳确认")
        items.append("若放量反弹+站上中轨，可小仓试多")
        if "较宽" in bw:
            items.append("带宽较宽+下轨：主跌浪可能，不接飞刀，严格止跌")
        items.append("若价格继续沿下轨下行，保持观望不抄底")

    elif "中上区间" in pos:
        items.append("中上区间运行：多头环境，可顺势持有")
        items.append("若价格回踩中轨获得支撑，是较好的加仓/入场点")
        items.append("关注上轨突破：放量突破上轨可追，缩量触及上轨不追")

    elif "中下区间" in pos:
        items.append("中下区间运行：空头环境，以观望为主")
        items.append("若价格反弹至中轨遇阻，是减仓机会")
        items.append("关注下轨支撑：若缩量回踩下轨企稳，可轻仓试反弹")

    # 收窄特殊提示
    if "收窄" in bw:
        items.append("布林带收窄：变盘前兆，提前做好双向准备，不预判方向")

    items.append("布林带信号需结合成交量与 MACD/RSI 综合判断")
    return items
