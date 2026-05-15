#!/usr/bin/env python
"""布林带策略 Web 仪表盘 - Flask 应用"""

import sys
import os
import threading
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, render_template, request

from src.config import get_config, ensure_dirs
from src.watchlist import load_watchlist, create_sample_watchlist
from src.data_fetcher import fetch_batch_data
from src.bollinger import calculate_bollinger
from src.signals import Signal
from src.indicators import calculate_macd, calculate_rsi
from src.indicator_interpreter import interpret_all
from src.squeeze import detect_squeeze_breakout, scan_squeeze_history, check_cross_validation
from src import cache

# 策略注册中心
from src.strategies import StrategyRegistry
from src.strategies.bollinger import BollingerStrategy
from src.strategies.dual_ma import DualMAStrategy
from src.strategies.dual_ma_interpreter import interpret_dual_ma_all

app = Flask(__name__)

# 注册所有策略
_registry = StrategyRegistry()
_registry.register(BollingerStrategy())
_registry.register(DualMAStrategy())

# 全局数据状态
_data_lock = threading.Lock()
_data_state = {
    "signals": [],
    "data_dict": {},
    "buy_count": 0,
    "sell_count": 0,
    "enhanced_count": 0,
    "total_stocks": 0,
    "scan_time": None,
    "loading": True,
    "error": None,
    "active_strategy": "bollinger",
}

# 参数实验室状态（不持久化，刷新页面即恢复默认）
_params_lock = threading.Lock()
_current_params = {"n": 20, "m": 2.0}
_current_strategy_id = "bollinger"


def _get_strategy():
    """获取当前活跃策略实例"""
    with _params_lock:
        sid = _current_strategy_id
    return _registry.get(sid)


def _scan_with_strategy(strategy, data_dict, params):
    """
    用指定策略扫描所有股票信号。

    Returns:
        (signals_list, new_data_dict)
    """
    signals = []
    new_data_dict = {}

    for symbol, (name, df) in data_dict.items():
        df_s = strategy.generate_signals(df, params)
        # 补充 MACD/RSI（如果策略没计算）
        if "macd" not in df_s.columns:
            df_s = calculate_macd(df_s)
        if "rsi" not in df_s.columns:
            df_s = calculate_rsi(df_s)
        new_data_dict[symbol] = (name, df_s)

        sig = strategy.create_signal(symbol, name, df_s, len(df_s) - 1, params)
        if sig:
            signals.append(sig)

    return signals, new_data_dict


def load_data():
    """加载数据：自选股 → 获取行情 → 计算指标 → 扫描信号"""
    global _data_state

    config = get_config()
    ensure_dirs()

    # 加载自选股
    watchlist_file = "watchlist.csv"
    if not os.path.exists(watchlist_file):
        create_sample_watchlist(watchlist_file)

    stocks = load_watchlist(watchlist_file)
    if len(stocks) == 0:
        with _data_lock:
            _data_state["error"] = "自选股为空"
            _data_state["loading"] = False
        return

    # 批量获取数据
    data_dict_raw, failed = fetch_batch_data(
        stocks=stocks,
        period=config.period,
        start_date=config.start_date,
        use_cache=True,
        request_interval=0.5,
    )

    # 计算基础指标（布林带 + MACD + RSI）
    data_dict_base = {}
    for stock in stocks:
        symbol = stock.symbol
        name = stock.name
        if symbol not in data_dict_raw:
            continue
        df = data_dict_raw[symbol]
        df = calculate_bollinger(df, n=config.bollinger_n, m=config.bollinger_m)
        df = calculate_macd(df, fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal)
        df = calculate_rsi(df, period=config.rsi_period)
        data_dict_base[symbol] = (name, df)
        cache.save_bollinger_history(symbol, name, df)

    # 用活跃策略扫描信号
    strategy = _get_strategy()
    params = strategy.get_default_params()
    signals, data_dict_full = _scan_with_strategy(strategy, data_dict_base, params)

    buy_count = len([s for s in signals if s.signal_type == "BUY"])
    sell_count = len([s for s in signals if s.signal_type == "SELL"])
    enhanced_count = len([s for s in signals if s.is_enhanced])

    # 保存缓存
    scan_time = datetime.now()
    cache.save_signals(signals)
    cache.save_metadata(
        config=config,
        scan_time=scan_time,
        buy_count=buy_count,
        sell_count=sell_count,
        enhanced_count=enhanced_count,
        total_stocks=len(data_dict_full),
    )

    with _data_lock:
        _data_state = {
            "signals": signals,
            "data_dict": data_dict_full,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "enhanced_count": enhanced_count,
            "total_stocks": len(data_dict_full),
            "scan_time": scan_time.isoformat(),
            "loading": False,
            "error": None,
            "active_strategy": strategy.strategy_id,
        }


def _signal_to_dict(s):
    return {
        "symbol": s.symbol,
        "name": s.name,
        "date": s.date,
        "signal_type": s.signal_type,
        "price": s.price,
        "strategy_id": s.strategy_id,
        "boll_up": s.boll_up,
        "boll_mid": s.boll_mid,
        "boll_down": s.boll_down,
        "volume_ratio": s.volume_ratio,
        "is_enhanced": s.is_enhanced,
        "metadata": s.metadata,
    }


# ─── 页面路由 ───────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


# ─── API 路由 ───────────────────────────────────────────

@app.route("/api/signals")
def api_signals():
    with _data_lock:
        signals = _data_state["signals"]
        meta = {
            "scan_time": _data_state["scan_time"],
            "buy_count": _data_state["buy_count"],
            "sell_count": _data_state["sell_count"],
            "enhanced_count": _data_state["enhanced_count"],
            "total_stocks": _data_state["total_stocks"],
            "loading": _data_state["loading"],
            "error": _data_state["error"],
            "strategy_id": _data_state.get("active_strategy", "bollinger"),
        }

    buy_signals = [_signal_to_dict(s) for s in signals if s.signal_type == "BUY"]
    sell_signals = [_signal_to_dict(s) for s in signals if s.signal_type == "SELL"]

    return jsonify(_sanitize_json({"buy_signals": buy_signals, "sell_signals": sell_signals, "meta": meta}))


@app.route("/api/stocks")
def api_stocks():
    with _data_lock:
        data_dict = _data_state["data_dict"]
        meta = {
            "scan_time": _data_state["scan_time"],
            "total_stocks": _data_state["total_stocks"],
            "loading": _data_state["loading"],
            "error": _data_state["error"],
            "strategy_id": _data_state.get("active_strategy", "bollinger"),
        }

    import pandas as pd

    stocks_list = []
    for symbol, (name, df) in data_dict.items():
        if len(df) == 0:
            continue

        latest = df.iloc[-1]
        close = _safe_float(latest.get("close")) or 0
        boll_up = _safe_float(latest.get("boll_up")) or 0
        boll_mid = _safe_float(latest.get("ma_mid")) or 0
        boll_down = _safe_float(latest.get("boll_down")) or 0
        volume_ratio = _safe_float(latest.get("volume_ratio"))

        # 判断布林带位置
        position = _boll_position(close, boll_up, boll_mid, boll_down)
        # 检查最新信号
        has_signal = None
        if "buy_signal" in df.columns and latest.get("buy_signal") == 1:
            has_signal = "BUY"
        elif "sell_signal" in df.columns and latest.get("sell_signal") == 1:
            has_signal = "SELL"

        # 趋势方向（双均线策略）
        trend = None
        if "ema_fast" in df.columns and "ema_slow" in df.columns:
            ef = _safe_float(latest.get("ema_fast"))
            es = _safe_float(latest.get("ema_slow"))
            if ef is not None and es is not None and es > 0:
                trend = "↗ 多头" if ef > es else "↘ 空头"

        stocks_list.append(
            {
                "symbol": symbol,
                "name": name,
                "close": close,
                "boll_up": boll_up,
                "boll_mid": boll_mid,
                "boll_down": boll_down,
                "position": position,
                "volume_ratio": volume_ratio,
                "has_signal": has_signal,
                "date": str(latest.get("date", "")),
                "ema_fast": _safe_float(latest.get("ema_fast")),
                "ema_slow": _safe_float(latest.get("ema_slow")),
                "trend": trend,
            }
        )

    return jsonify(_sanitize_json({"stocks": stocks_list, "meta": meta}))


# ─── 策略 API ───────────────────────────────────────────

@app.route("/api/strategies")
def api_strategies():
    """返回所有已注册策略"""
    with _params_lock:
        active = _current_strategy_id
    return jsonify({
        "strategies": _registry.list_all(),
        "active": active,
    })


@app.route("/api/strategy/switch", methods=["POST"])
def api_strategy_switch():
    """切换活跃策略"""
    body = request.get_json(silent=True) or {}
    new_id = body.get("strategy", "bollinger")

    strategy = _registry.get(new_id)
    if strategy is None:
        return jsonify({"error": f"未知策略: {new_id}"}), 400

    global _current_strategy_id, _current_params
    with _params_lock:
        _current_strategy_id = strategy.strategy_id
        _current_params = dict(strategy.get_default_params())

    with _data_lock:
        if not _data_state["data_dict"]:
            return jsonify({"error": "数据未就绪"}), 400

    threading.Thread(target=_background_param_recalc, args=(strategy, _current_params), daemon=True).start()
    return jsonify({"success": True, "loading": True, "strategy": strategy.strategy_id})


# ─── 参数实验室 API ──────────────────────────────────────

def _validate_params(body, schema):
    """从 body 和 schema 中解析并验证参数"""
    params = {}
    for field in schema:
        key = field["key"]
        try:
            if field.get("step", 1) >= 1:
                val = int(body.get(key, field["default"]))
            else:
                val = float(body.get(key, field["default"]))
        except (ValueError, TypeError):
            return None, f"{key} 必须是数字"
        if val < field["min"] or val > field["max"]:
            return None, f"{key} 范围 {field['min']}-{field['max']}"
        params[key] = val
    return params, None


@app.route("/api/params")
def api_params():
    with _data_lock:
        data_dict_snap = dict(_data_state["data_dict"])
        loading = _data_state["loading"]

    strategy = _get_strategy()
    with _params_lock:
        current = dict(_current_params)

    market_snapshot = _compute_market_snapshot(data_dict_snap) if not loading and data_dict_snap else {
        "avg_bandwidth": 0, "avg_std": 0, "volatility_trend": "数据未就绪"
    }

    return jsonify(_sanitize_json({
        "strategy_id": strategy.strategy_id,
        "strategy_name": strategy.strategy_name,
        "current_params": current,
        "params_schema": strategy.get_params_schema(),
        "presets": strategy.get_presets(),
        "market_snapshot": market_snapshot,
        "loading": loading,
    }))


@app.route("/api/params/preview", methods=["POST"])
def api_params_preview():
    body = request.get_json(silent=True) or {}
    strategy = _get_strategy()
    schema = strategy.get_params_schema()

    params, err = _validate_params(body, schema)
    if err:
        return jsonify({"error": err}), 400

    with _data_lock:
        data_dict = _data_state["data_dict"]
        loading = _data_state["loading"]
        current_buy = _data_state["buy_count"]
        current_sell = _data_state["sell_count"]

    if loading or not data_dict:
        return jsonify({"error": "数据未就绪"}), 400

    # 用新参数在内存中预览
    preview_dict = {}
    for symbol, (name, df) in data_dict.items():
        df_p = strategy.generate_signals(df.copy(), params)
        preview_dict[symbol] = (name, df_p)

    preview_signals, _ = _scan_with_strategy(strategy, preview_dict, params)
    preview_buy = sum(1 for s in preview_signals if s.signal_type == "BUY")
    preview_sell = sum(1 for s in preview_signals if s.signal_type == "SELL")

    return jsonify(_sanitize_json({
        "current": {"buy": current_buy, "sell": current_sell},
        "preview": {"buy": preview_buy, "sell": preview_sell},
    }))


@app.route("/api/params", methods=["POST"])
def api_params_apply():
    body = request.get_json(silent=True) or {}
    strategy = _get_strategy()
    schema = strategy.get_params_schema()

    params, err = _validate_params(body, schema)
    if err:
        return jsonify({"error": err}), 400

    global _current_params
    with _params_lock:
        _current_params = dict(params)

    threading.Thread(target=_background_param_recalc, args=(strategy, params), daemon=True).start()
    return jsonify({"success": True, "loading": True})


@app.route("/api/stock/<symbol>")
def api_stock_detail(symbol):
    with _data_lock:
        data_dict = _data_state["data_dict"]

    if symbol not in data_dict:
        return jsonify({"error": f"股票 {symbol} 不在自选股中"}), 404

    import pandas as pd

    name, df = data_dict[symbol]

    # 确保有信号列
    if "buy_signal" not in df.columns or "sell_signal" not in df.columns:
        from src.signals import generate_signals

        df = generate_signals(df)

    # 转换 DataFrame 为 JSON（最近 120 条，前端渲染足够）
    df_display = df.tail(120).copy()
    df_display["date"] = df_display["date"].astype(str)

    # 选择需要的列
    cols = ["date", "open", "high", "low", "close", "volume"]
    extra_cols = [c for c in ["ma_mid", "boll_up", "boll_down", "buy_signal", "sell_signal",
                              "macd", "macd_signal", "macd_histogram", "rsi",
                              "ema_fast", "ema_slow"] if c in df_display.columns]
    all_cols = cols + extra_cols

    history = df_display[all_cols].to_dict(orient="records")

    # 最新数据
    latest = df.iloc[-1]
    latest_sanitized = {
        "close": _safe_float(latest.get("close")),
        "macd": _safe_float(latest.get("macd")),
        "macd_signal": _safe_float(latest.get("macd_signal")),
        "macd_histogram": _safe_float(latest.get("macd_histogram")),
        "rsi": _safe_float(latest.get("rsi")),
        "boll_up": _safe_float(latest.get("boll_up")),
        "boll_mid": _safe_float(latest.get("ma_mid")),
        "boll_down": _safe_float(latest.get("boll_down")),
    }

    # 前一周期数据（用于趋势对比）
    prev_sanitized = {}
    if len(history) >= 2:
        p = history[-2]
        prev_sanitized = {
            "macd": _safe_float(p.get("macd")),
            "macd_signal": _safe_float(p.get("macd_signal")),
            "macd_histogram": _safe_float(p.get("macd_histogram")),
            "rsi": _safe_float(p.get("rsi")),
        }

    interpretation = interpret_all(latest_sanitized, prev_sanitized)

    # 策略感知：当前策略 ID
    current_strategy_id = _current_strategy_id

    # 双均线策略专属解读
    dual_ma_interpretation = None
    if current_strategy_id == "dual_ma":
        dual_ma_interpretation = interpret_dual_ma_all(df)

    # 收口突破检测（仅布林带策略）
    squeeze_data = None
    if current_strategy_id != "dual_ma":
        df_squeeze = detect_squeeze_breakout(df)
        latest_sq = df_squeeze.iloc[-1]
        squeeze_data = {
            "is_squeeze": bool(latest_sq.get("is_squeeze", False)),
            "bandwidth_pct": _safe_float(latest_sq.get("band_width_pct")),
            "breakout_direction": latest_sq.get("breakout_direction") or None,
            "cross_validation": "neutral",
            "history": [],
        }
        if squeeze_data["breakout_direction"]:
            squeeze_data["cross_validation"] = check_cross_validation(
                squeeze_data["breakout_direction"], latest_sq
            )
        squeeze_data["history"] = scan_squeeze_history(df)

    response_data = {
        "symbol": symbol,
        "name": name,
        "strategy_id": current_strategy_id,
        "latest": {
            "date": str(latest.get("date", "")),
            "close": latest_sanitized["close"],
            "boll_up": latest_sanitized["boll_up"],
            "boll_mid": latest_sanitized["boll_mid"],
            "boll_down": latest_sanitized["boll_down"],
            "volume_ratio": _safe_float(latest.get("volume_ratio")),
            "buy_signal": int(latest.get("buy_signal", 0)) if "buy_signal" in latest and not pd.isna(latest.get("buy_signal")) else 0,
            "sell_signal": int(latest.get("sell_signal", 0)) if "sell_signal" in latest and not pd.isna(latest.get("sell_signal")) else 0,
            "macd": latest_sanitized["macd"],
            "macd_signal": latest_sanitized["macd_signal"],
            "macd_histogram": latest_sanitized["macd_histogram"],
            "rsi": latest_sanitized["rsi"],
        },
        "history": history,
        "interpretation": interpretation,
        "squeeze": squeeze_data,
        "dual_ma_interpretation": dual_ma_interpretation,
    }

    return jsonify(_sanitize_json(response_data))


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    try:
        # 重置参数实验室参数为默认值
        strategy = _get_strategy()
        defaults = strategy.get_default_params()
        global _current_params
        with _params_lock:
            _current_params = dict(defaults)
        with _data_lock:
            _data_state["loading"] = True
        load_data()
        with _data_lock:
            return jsonify(
                {
                    "success": True,
                    "meta": {
                        "scan_time": _data_state["scan_time"],
                        "buy_count": _data_state["buy_count"],
                        "sell_count": _data_state["sell_count"],
                        "enhanced_count": _data_state["enhanced_count"],
                        "total_stocks": _data_state["total_stocks"],
                        "active_strategy": _data_state.get("active_strategy", "bollinger"),
                    },
                }
            )
    except Exception as e:
        with _data_lock:
            _data_state["loading"] = False
            _data_state["error"] = str(e)
        return jsonify({"success": False, "error": str(e)}), 500


def _safe_float(val, default=None):
    """将值转为 float，NaN/Inf 转为 None（JSON 兼容）"""
    try:
        f = float(val)
        import math
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _sanitize_json(obj):
    """递归清理对象中的 NaN/Inf 为 None（JSON 兼容）"""
    import math
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _boll_position(close, boll_up, boll_mid, boll_down):
    """判断价格在布林带中的位置"""
    if boll_up <= boll_down:
        return "-"
    if close >= boll_up:
        return "上轨附近"
    if close <= boll_down:
        return "下轨附近"
    if close >= boll_mid:
        return "中上区间"
    return "中下区间"


def _compute_market_snapshot(data_dict):
    """计算全市场特征速览：平均带宽、平均波动率、波动率趋势"""
    import math

    if not data_dict:
        return {"avg_bandwidth": 0, "avg_std": 0, "volatility_trend": "数据未就绪"}

    bandwidths = []
    stds_recent = []
    stds_older = []

    for _symbol, (_name, df) in data_dict.items():
        if len(df) < 2:
            continue
        latest = df.iloc[-1]
        b_up = _safe_float(latest.get("boll_up"))
        b_mid = _safe_float(latest.get("ma_mid"))
        b_down = _safe_float(latest.get("boll_down"))

        if b_up is not None and b_mid is not None and b_down is not None and b_mid > 0:
            bandwidth = (b_up - b_down) / b_mid
            if not math.isnan(bandwidth) and not math.isinf(bandwidth):
                bandwidths.append(bandwidth)

        if "std" in df.columns:
            std_col = df["std"].dropna()
            if len(std_col) >= 5:
                stds_recent.append(float(std_col.iloc[-5:].mean()))
                stds_older.append(float(std_col.iloc[-20:-5].mean()) if len(std_col) >= 20 else float(std_col.iloc[-5:].mean()))

    avg_bandwidth = round(sum(bandwidths) / len(bandwidths), 4) if bandwidths else 0
    avg_std = round(sum(s[0] for s in [stds_recent] if s) / len(stds_recent), 3) if stds_recent else 0

    if stds_recent and stds_older:
        recent_avg = sum(stds_recent) / len(stds_recent)
        older_avg = sum(stds_older) / len(stds_older)
        if older_avg > 0:
            change = (recent_avg - older_avg) / older_avg
            if change > 0.05:
                volatility_trend = "上升 ↑"
            elif change < -0.05:
                volatility_trend = "下降 ↓"
            else:
                volatility_trend = "平稳"
        else:
            volatility_trend = "平稳"
    else:
        volatility_trend = "数据不足"

    return {
        "avg_bandwidth": avg_bandwidth,
        "avg_std": avg_std,
        "volatility_trend": volatility_trend,
    }


def _background_param_recalc(strategy, params):
    """后台线程：用策略的新参数重算信号，更新 _data_state"""
    global _data_state

    with _data_lock:
        data_dict_snap = dict(_data_state["data_dict"])
        _data_state["loading"] = True

    if not data_dict_snap:
        with _data_lock:
            _data_state["loading"] = False
            _data_state["error"] = "无数据可供重算"
        return

    try:
        # 如果是布林带策略，需重算布林带列（参数 n/m 影响显示）
        if strategy.strategy_id == "bollinger":
            from src.bollinger import calculate_bollinger
            n_ = int(params.get("n", 20))
            m_ = float(params.get("m", 2.0))
            base_dict = {}
            for symbol, (name, df) in data_dict_snap.items():
                df_r = df.copy()
                df_r = calculate_bollinger(df_r, n=n_, m=m_)
                base_dict[symbol] = (name, df_r)
        else:
            base_dict = data_dict_snap

        signals, new_data_dict = _scan_with_strategy(strategy, base_dict, params)

        # 补充 Bollinger（非布林策略保留用于展示）
        if strategy.strategy_id != "bollinger":
            for symbol, (name, df) in new_data_dict.items():
                if "boll_up" not in df.columns or "boll_down" not in df.columns:
                    from src.bollinger import calculate_bollinger
                    df = calculate_bollinger(df)

        buy_count = sum(1 for s in signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in signals if s.signal_type == "SELL")
        enhanced_count = sum(1 for s in signals if s.is_enhanced)
        scan_time = datetime.now()

        with _data_lock:
            _data_state["signals"] = signals
            _data_state["data_dict"] = new_data_dict
            _data_state["buy_count"] = buy_count
            _data_state["sell_count"] = sell_count
            _data_state["enhanced_count"] = enhanced_count
            _data_state["total_stocks"] = len(new_data_dict)
            _data_state["scan_time"] = scan_time.isoformat()
            _data_state["loading"] = False
            _data_state["error"] = None
            _data_state["active_strategy"] = strategy.strategy_id
    except Exception as e:
        with _data_lock:
            _data_state["loading"] = False
            _data_state["error"] = str(e)


def load_cached_data():
    """从本地缓存加载数据到内存（不访问网络，秒级完成）"""
    global _data_state
    config = get_config()
    ensure_dirs()

    import pandas as pd

    # 加载元数据
    meta = cache.load_metadata()
    # 加载信号
    signals_df = cache.load_signals()
    # 加载布林带缓存目录
    bollinger_dir = config.cache_bollinger_dir
    data_dict = {}
    signals_list = []

    if os.path.isdir(bollinger_dir):
        for fname in os.listdir(bollinger_dir):
            if not fname.endswith(".csv"):
                continue
            filepath = os.path.join(bollinger_dir, fname)
            try:
                df = pd.read_csv(filepath)
                # 从文件名解析 symbol: {name}_{symbol}.csv
                base = fname[:-4]
                parts = base.rsplit("_", 1)
                if len(parts) == 2:
                    name_part, symbol = parts
                else:
                    symbol = base
                    name_part = symbol
                # 确保有信号列
                if "buy_signal" not in df.columns:
                    from src.signals import generate_signals
                    df = generate_signals(df)
                # 确保有 MACD/RSI 列
                if "macd" not in df.columns:
                    df = calculate_macd(df)
                if "rsi" not in df.columns:
                    df = calculate_rsi(df)
                data_dict[symbol] = (name_part, df)
            except Exception:
                pass

    if signals_df is not None and len(signals_df) > 0:
        for _, row in signals_df.iterrows():
            s = Signal(
                symbol=str(row.get("symbol", "")),
                name=str(row.get("name", "")),
                date=str(row.get("date", "")),
                signal_type=str(row.get("signal_type", "NONE")),
                price=float(row.get("price", 0)),
                strategy_id=str(row.get("strategy_id", "bollinger")),
                boll_up=float(row["boll_up"]) if pd.notna(row.get("boll_up")) else None,
                boll_mid=float(row["boll_mid"]) if pd.notna(row.get("boll_mid")) else None,
                boll_down=float(row["boll_down"]) if pd.notna(row.get("boll_down")) else None,
                volume_ratio=float(row["volume_ratio"]) if pd.notna(row.get("volume_ratio")) else None,
                is_enhanced=bool(row.get("is_enhanced", False)),
            )
            signals_list.append(s)

    buy_count = len([s for s in signals_list if s.signal_type == "BUY"])
    sell_count = len([s for s in signals_list if s.signal_type == "SELL"])
    enhanced_count = len([s for s in signals_list if s.is_enhanced])

    with _data_lock:
        _data_state = {
            "signals": signals_list,
            "data_dict": data_dict,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "enhanced_count": enhanced_count,
            "total_stocks": len(data_dict),
            "scan_time": meta.get("scan_time") if meta else None,
            "loading": len(data_dict) == 0,
            "error": None,
            "active_strategy": "bollinger",
        }


def background_refresh():
    """后台线程：拉取最新数据并更新 _data_state"""
    try:
        load_data()
    except Exception as e:
        with _data_lock:
            _data_state["loading"] = False
            _data_state["error"] = str(e)


if __name__ == "__main__":
    print("=" * 60)
    print("📊 布林带策略 Web 仪表盘")
    print("=" * 60)

    # 1. 先从缓存加载（秒级）
    print("正在加载缓存数据...")
    load_cached_data()
    print(f"✅ 缓存加载完成: {_data_state['total_stocks']} 只股票")

    # 2. 启动 Flask
    print(f"\n🌐 访问地址: http://localhost:5001")

    # 3. 启动后台刷新线程
    refresh_thread = threading.Thread(target=background_refresh, daemon=True)
    refresh_thread.start()
    print("🔄 后台刷新最新数据中...")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5001, debug=False)
