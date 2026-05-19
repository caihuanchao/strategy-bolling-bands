# 单只股票手动刷新

## Problem Statement

如何让用户在不触发全量刷新（44 只股票遍历）的情况下，针对性地更新某一两只股票的数据，快速查看最新行情和信号。

## Recommended Direction

**新增 `POST /api/stock/<symbol>/refresh` 端点 + 个股管理表格中 🔄 按钮**。

后端：拉取单只股票数据 → 计算全部指标 → merge 到现有 `data_dict` → 重新扫描全部信号 → 更新 `_data_state`。
前端：个股管理 Tab 的操作列新增 🔄 图标按钮。

### 后端实现

**`app.py` 新增端点**：

```python
@app.route("/api/stock/<symbol>/refresh", methods=["POST"])
def api_stock_refresh(symbol):
    """手动刷新单只股票数据"""
    # 1. 找到该股票信息
    stocks = load_watchlist()
    stock_info = None
    for s in stocks:
        if s.symbol == symbol:
            stock_info = s
            break
    if stock_info is None:
        return jsonify({"success": False, "error": f"股票 {symbol} 未找到"}), 404

    # 2. 拉取最新数据（force_refresh）
    config = get_config()
    try:
        df = get_stock_data(
            symbol=symbol, period=config.period,
            start_date=config.start_date, name=stock_info.name,
            force_refresh=True,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # 3. 计算全部指标
    df = calculate_bollinger(df, n=config.bollinger_n, m=config.bollinger_m)
    df = calculate_macd(df, fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal)
    df = calculate_rsi(df, period=config.rsi_period)
    df = calculate_obv(df)
    df = calculate_volume_ratio(df)

    # 4. 运行当前策略信号生成
    strategy = _get_strategy()
    params = strategy.get_default_params()
    df = strategy.generate_signals(df, params)
    if "macd" not in df.columns:
        df = calculate_macd(df)
    if "rsi" not in df.columns:
        df = calculate_rsi(df)

    # 5. 合并到现有 data_dict，重新扫描全部信号
    with _data_lock:
        merged_dict = dict(_data_state.get("data_dict", {}))
        merged_dict[symbol] = (stock_info.name, df)
    all_signals, _ = _scan_with_strategy(strategy, merged_dict, params)
    buy_count = len([s for s in all_signals if s.signal_type == "BUY"])
    sell_count = len([s for s in all_signals if s.signal_type == "SELL"])
    enhanced_count = len([s for s in all_signals if s.is_enhanced])

    # 6. 更新全局状态 + 保存缓存
    scan_time = datetime.now()
    cache.save_signals(all_signals)
    cache.save_metadata(config=config, scan_time=scan_time,
                       buy_count=buy_count, sell_count=sell_count,
                       enhanced_count=enhanced_count,
                       total_stocks=len(merged_dict))

    with _data_lock:
        _data_state.update({
            "signals": all_signals, "data_dict": merged_dict,
            "buy_count": buy_count, "sell_count": sell_count,
            "enhanced_count": enhanced_count,
            "total_stocks": len(merged_dict),
            "scan_time": scan_time.isoformat(), "loading": False,
            "error": None,
        })

    return jsonify({
        "success": True,
        "symbol": symbol,
        "name": stock_info.name,
        "meta": {
            "scan_time": scan_time.isoformat(),
            "buy_count": buy_count, "sell_count": sell_count,
            "enhanced_count": enhanced_count,
            "total_stocks": len(merged_dict),
        },
    })
```

### 前端实现

**`templates/dashboard.html` — 个股管理表格操作列**：

在删除按钮前新增 🔄 按钮：

```html
<button onclick="refreshStock('${s.symbol}')" title="刷新数据" style="...">🔄</button>
```

**新增 JS 函数**：

```javascript
async function refreshStock(symbol) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳';
    try {
        const res = await fetch(`/api/stock/${symbol}/refresh`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            loadWatchlistManager();        // 刷新管理页
            await loadSignals();           // 刷新信号面板
        } else {
            alert('刷新失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('刷新请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄';
    }
}
```

### 文件清单

| 文件 | 改动 |
|------|------|
| `app.py` | 新增 `POST /api/stock/<symbol>/refresh` 端点（~40 行）；新增 `from src.data_fetcher import get_stock_data` 导入 |
| `templates/dashboard.html` | 个股管理表格每行新增 🔄 按钮 + `refreshStock()` JS 函数 |

## Key Assumptions

- [ ] `get_stock_data(force_refresh=True)` 能单独拉取单只股票（验证方式：curl POST /api/stock/600900/refresh）
- [ ] 单只刷新后 `_scan_with_strategy` 重扫全部信号耗时可接受（~40 只股票，纯内存操作 < 1s）
- [ ] 前端在信号面板刷新期间不会出现状态不一致（已有 `loading` 状态机制）

## MVP Scope

**In scope:**
- `POST /api/stock/<symbol>/refresh` 端点
- 个股管理表格每行 🔄 按钮
- 刷新后自动更新信号面板

**Out of scope:**
- 信号表格中的刷新按钮（仅个股管理 Tab）
- 批量选中多只股票刷新
- 刷新进度条或 loading 动画（单只股票拉取很快）
- 刷新历史记录

## Not Doing (and Why)

- **信号表格页添加刷新按钮** — 增加视觉噪声，个股管理 Tab 是管理操作的集中入口
- **批量刷新** — 增加 UI 复杂度（多选复选框），当前无明确需求
- **提取共享辅助函数 `_refresh_and_merge()`** — 只有 `load_data()` 分组更新和本端点共用该逻辑，两处重复可接受
- **刷新队列/并发控制** — 单用户场景，不会有并发刷新请求

## Open Questions

- 无
