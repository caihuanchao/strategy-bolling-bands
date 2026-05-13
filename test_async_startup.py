#!/usr/bin/env python
"""TDD tests for cache-first startup with background async refresh"""

import sys
import os
import json
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as app_module


def test_load_cached_data_loads_from_cache():
    """Test 1: load_cached_data() 从已有缓存加载数据到 _data_state"""
    app_module.load_cached_data()

    state = app_module._data_state
    assert state["error"] is None, f"error should be None, got: {state['error']}"
    assert not state["loading"], "loading should be False after cache load"
    assert state["total_stocks"] > 0, f"Expected stocks > 0 from cache, got {state['total_stocks']}"
    print(f"  PASS: loaded {state['total_stocks']} stocks from cache")


def test_load_cached_data_no_crash_on_missing_data():
    """Test 2: load_cached_data() 在部分缓存缺失时不崩溃"""
    # 验证 signals_df 为 None 时不崩溃（正常情况）
    import pandas as pd
    import src.cache as cache_mod

    # load_signals 可能返回 None（无缓存），验证不崩溃
    sigs = cache_mod.load_signals()
    meta = cache_mod.load_metadata()
    print(f"  signals cached: {sigs is not None}, metadata cached: {meta is not None}")

    # 核心验证：函数调用成功，不抛异常
    app_module.load_cached_data()
    state = app_module._data_state
    assert state["error"] is None, f"error should be None: {state['error']}"
    assert "total_stocks" in state
    print(f"  PASS: handled with {state['total_stocks']} stocks from cache")


def test_api_returns_loading_during_refresh():
    """Test 3: 后台刷新期间 API 返回 loading=True"""
    with app_module._data_lock:
        app_module._data_state["loading"] = True

    with app_module.app.test_client() as client:
        resp = client.get("/api/signals")
        data = resp.get_json()
        assert data["meta"]["loading"] == True, f"Expected loading=True"

        resp2 = client.get("/api/stocks")
        data2 = resp2.get_json()
        assert data2["meta"]["loading"] == True

    with app_module._data_lock:
        app_module._data_state["loading"] = False
    print("  PASS: API returns loading=True during refresh")


def test_flask_responds_immediately_after_cache_load():
    """Test 4: Flask 在缓存加载后立即响应请求"""
    app_module.load_cached_data()

    with app_module.app.test_client() as client:
        start = time.time()
        resp = client.get("/")
        elapsed = time.time() - start

        assert resp.status_code == 200
        assert elapsed < 0.5, f"Page load took {elapsed:.2f}s, expected < 0.5s"
        print(f"  PASS: page loaded in {elapsed:.3f}s")


def test_background_refresh_updates_state():
    """Test 5 (optional, needs network): background_refresh 完成后状态更新"""
    app_module.load_cached_data()

    thread = threading.Thread(target=app_module.background_refresh, daemon=True)
    thread.start()
    thread.join(timeout=120)

    state = app_module._data_state
    assert state["error"] is None, f"Refresh error: {state['error']}"
    assert not state["loading"], f"Expected loading=False after refresh"
    assert state["total_stocks"] > 0, f"Expected stocks > 0 after refresh, got {state['total_stocks']}"
    print(f"  PASS: background refresh completed, {state['total_stocks']} stocks loaded")


if __name__ == "__main__":
    print("=" * 60)
    print("TDD Tests: Cache-first startup + background refresh")
    print("=" * 60)

    tests = [
        ("load_cached_data loads from cache", test_load_cached_data_loads_from_cache),
        ("load_cached_data no crash", test_load_cached_data_no_crash_on_missing_data),
        ("API loading state during refresh", test_api_returns_loading_during_refresh),
        ("Flask responds immediately", test_flask_responds_immediately_after_cache_load),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\nTest 5 (background_refresh) is optional - run with:")
        print("  python -c 'from test_async_startup import test_background_refresh_updates_state; test_background_refresh_updates_state()'")
