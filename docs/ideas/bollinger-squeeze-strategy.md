# 布林带收口突破策略

## Problem Statement

如何在现有布林带策略工作台中检测"布林带收口→价格突破"形态，在个股详情页中展示当前收口状态和历史突破事件，从而识别盘整蓄力后的爆发性行情？

## Recommended Direction

**方案 D：独立模块 `src/squeeze.py` + 轻量历史扫描**

新增独立模块 `src/squeeze.py`，包含两个核心函数：
- `detect_squeeze_breakout(df)` — 计算当前收口状态和最新突破方向
- `scan_squeeze_history(df)` — 扫描完整历史上所有收口→突破事件，返回事件列表

在 `GET /api/stock/{symbol}` 的响应中新增 `squeeze` 字段，前端在个股详情弹窗中展示：
- 收口状态卡片（当前是否收口中 + 带宽百分比）
- 突破方向标记（向上突破 / 向下突破 / 无）
- 历史突破事件时间线（日期、方向、放量情况）

参数固定：收口阈值 10%，放量确认 1.5×10 日均量，不暴露 UI。

## Key Assumptions to Validate

- [ ] **0.1 收口阈值对 A 股适用** — 取 3-5 只典型股票验证，确认不会过度触发或几乎不触发
- [ ] **历史事件列表长度合理** — 扫描一只股票 2 年数据，确认事件数不会超过 15-20 条（否则需要加过滤条件）
- [ ] **个股详情页信息密度可接受** — 新增内容不导致模态窗过长或加载变慢

## MVP Scope

**包含：**

1. 新模块 `src/squeeze.py`：
   - `detect_squeeze_breakout(df)` → DataFrame 增加 `band_width_pct`、`is_squeeze`、`breakout_direction` 列，返回 df
   - `scan_squeeze_history(df)` → 返回 `[{date, direction, bandwidth_pct, volume_ratio}]` 事件列表
2. 在 `GET /api/stock/{symbol}` 中调用，响应新增 `squeeze` 字段：
   ```json
   {
     "squeeze": {
       "is_squeeze": true,
       "bandwidth_pct": 0.087,
       "breakout_direction": "up",
       "history": [{"date": "2026-03-15", "direction": "up", "volume_ratio": 1.8}, ...]
     }
   }
   ```
3. 前端个股详情弹窗新增"收口突破"卡片（在三个解读卡片上方或下方），展示当前状态 + 最近 5 条历史事件

**技术约束：**
- `src/squeeze.py` 完全不依赖 `app.py`，纯 pandas 计算
- 假设输入的 df 已包含 `close`、`volume`、`boll_up`、`boll_down`、`ma_mid` 列
- `scan_squeeze_history` 只返回最近 20 条事件，避免数据过大

## Not Doing (and Why)

- **不做独立信号列表/Tab 页** — 收口突破作为辅助观察维度，不是独立交易信号，混入主信号列表会稀释信噪比
- **不做回测** — 用户明确选择"仅信号扫描"，验证收口突破策略的胜率/盈亏比是后续阶段的事
- **不做参数 UI** — 收口阈值和放量倍数固定默认值，不接入参数实验室
- **不做多周期收口** — 1h/4h 周期的收口检测需要额外数据加载，MVP 仅日线
- **不做收口前的预警** — 不做"接近收口"的提前提示，只在已收口状态下做检测

## Open Questions

1. `scan_squeeze_history` 中连续突破事件如何处理？如果连续 3 天都满足突破条件，是合并为一个事件还是各自记录？合并：取连续突破中 volume_ratio 最大的一天作为代表
2. 如果一只股票从未收口过（带宽一直 >10%），历史事件列表为空，前端不需要特殊空态提示
3. 收口突破方向是否应该与现有布林带信号做交叉验证？是，（例如：向上突破 + 现有买入信号 = 更强确认）
