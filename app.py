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
from src.signals import scan_all_signals, Signal
from src.indicators import calculate_macd, calculate_rsi
from src import cache

app = Flask(__name__)

# 全局状态
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
}


def load_data():
    """加载数据：自选股 → 获取行情 → 计算布林带 → 扫描信号"""
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

    # 计算布林带
    data_dict_full = {}
    for stock in stocks:
        symbol = stock.symbol
        name = stock.name
        if symbol not in data_dict_raw:
            continue
        df = data_dict_raw[symbol]
        df = calculate_bollinger(df, n=config.bollinger_n, m=config.bollinger_m)
        df = calculate_macd(df, fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal)
        df = calculate_rsi(df, period=config.rsi_period)
        data_dict_full[symbol] = (name, df)
        cache.save_bollinger_history(symbol, name, df)

    # 扫描信号
    volume_threshold = 1.5
    volume_window = 20
    signals = scan_all_signals(
        data_dict=data_dict_full,
        volume_threshold=volume_threshold,
        volume_window=volume_window,
    )

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
        }


def _signal_to_dict(s):
    return {
        "symbol": s.symbol,
        "name": s.name,
        "date": s.date,
        "signal_type": s.signal_type,
        "price": s.price,
        "boll_up": s.boll_up,
        "boll_mid": s.boll_mid,
        "boll_down": s.boll_down,
        "volume_ratio": s.volume_ratio,
        "is_enhanced": s.is_enhanced,
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
            }
        )

    return jsonify(_sanitize_json({"stocks": stocks_list, "meta": meta}))


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
                              "macd", "macd_signal", "macd_histogram", "rsi"] if c in df_display.columns]
    all_cols = cols + extra_cols

    history = df_display[all_cols].to_dict(orient="records")

    # 最新数据
    latest = df.iloc[-1]
    return jsonify(_sanitize_json(
        {
            "symbol": symbol,
            "name": name,
            "latest": {
                "date": str(latest.get("date", "")),
                "close": _safe_float(latest.get("close")),
                "boll_up": _safe_float(latest.get("boll_up")),
                "boll_mid": _safe_float(latest.get("ma_mid")),
                "boll_down": _safe_float(latest.get("boll_down")),
                "volume_ratio": _safe_float(latest.get("volume_ratio")),
                "buy_signal": int(latest.get("buy_signal", 0)) if "buy_signal" in latest and not pd.isna(latest.get("buy_signal")) else 0,
                "sell_signal": int(latest.get("sell_signal", 0)) if "sell_signal" in latest and not pd.isna(latest.get("sell_signal")) else 0,
                "macd": _safe_float(latest.get("macd")),
                "macd_signal": _safe_float(latest.get("macd_signal")),
                "macd_histogram": _safe_float(latest.get("macd_histogram")),
                "rsi": _safe_float(latest.get("rsi")),
            },
            "history": history,
        }
    ))


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    try:
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
                boll_up=float(row.get("boll_up", 0)),
                boll_mid=float(row.get("boll_mid", 0)),
                boll_down=float(row.get("boll_down", 0)),
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
