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

    return jsonify({"buy_signals": buy_signals, "sell_signals": sell_signals, "meta": meta})


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
        close = float(latest.get("close", 0))
        boll_up = float(latest.get("boll_up", 0))
        boll_mid = float(latest.get("ma_mid", 0))
        boll_down = float(latest.get("boll_down", 0))
        volume_ratio = (
            float(latest["volume_ratio"])
            if "volume_ratio" in latest and pd.notna(latest["volume_ratio"])
            else None
        )

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

    return jsonify({"stocks": stocks_list, "meta": meta})


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
    extra_cols = [c for c in ["ma_mid", "boll_up", "boll_down", "buy_signal", "sell_signal"] if c in df_display.columns]
    all_cols = cols + extra_cols

    history = df_display[all_cols].to_dict(orient="records")

    # 最新数据
    latest = df.iloc[-1]
    return jsonify(
        {
            "symbol": symbol,
            "name": name,
            "latest": {
                "date": str(latest.get("date", "")),
                "close": float(latest.get("close", 0)),
                "boll_up": float(latest.get("boll_up", 0)),
                "boll_mid": float(latest.get("ma_mid", 0)),
                "boll_down": float(latest.get("boll_down", 0)),
                "volume_ratio": (
                    float(latest["volume_ratio"])
                    if "volume_ratio" in latest and pd.notna(latest["volume_ratio"])
                    else None
                ),
                "buy_signal": int(latest.get("buy_signal", 0)) if "buy_signal" in latest else 0,
                "sell_signal": int(latest.get("sell_signal", 0)) if "sell_signal" in latest else 0,
            },
            "history": history,
        }
    )


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


if __name__ == "__main__":
    print("=" * 60)
    print("📊 布林带策略 Web 仪表盘")
    print("=" * 60)
    print("正在加载数据...")
    load_data()
    print(f"✅ 数据加载完成: {_data_state['total_stocks']} 只股票")
    print(f"   买入信号: {_data_state['buy_count']}")
    print(f"   卖出信号: {_data_state['sell_count']}")
    print(f"   增强信号: {_data_state['enhanced_count']}")
    print(f"\n🌐 访问地址: http://localhost:5001")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5001, debug=True)
