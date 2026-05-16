# MACD + RSI + 成交量三重确认策略

## Problem Statement
如何将 MACD+RSI+成交量三重确认策略集成到现有仪表盘，为用户提供带可靠性分级（C/B/A/S）的高确信信号，替代简单二元买卖信号？

## Recommended Direction
完整实现策略文档中的所有可落地功能：四级信号分级、ADX 震荡过滤、MA50 趋势过滤、周线多时间框架确认、三窗图表可视化、进出场条件展示。对不适合仪表盘的实盘交易功能（仓位管理、实时持仓追踪）做适配替换。

## 实施范围

### 新增文件
- `src/strategies/triple_confirm.py` — TripleConfirmStrategy 策略类
- `src/strategies/triple_confirm_interpreter.py` — 结构化中文解读

### 修改文件
- `app.py` — 注册新策略、股票详情 API 增加策略专属字段
- `src/indicators.py` — 新增 `calculate_adx()` 函数
- `src/config.py` — 新增 ADX/MACD/RSI 默认参数（已有大部分）
- `templates/dashboard.html` — 三窗图表 + 图例 + 信号等级展示

### 策略实现要点

**1. 信号分级 (generate_signals)**
- C 级：仅 MACD 金叉/死叉 → buy_signal=1, signal_grade="C"
- B 级：MACD 交叉 + RSI 配合（30-65 区间且方向向上）→ grade="B"
- A 级：B 级条件 + 成交量 ≥ 20日均量 1.0x + 缩量止跌后放量起涨 → grade="A"
- S 级：MACD 底背离 + RSI 底背离 + 放量阳线(量比>1.5) + MACD 金叉确认 → grade="S"

**2. 辅助指标**
- ADX(14)：ADX < 20 时所有信号降级或抑制（最大失败模式对策）
- MA50 趋势过滤：MA50 向上→允许做多，向下→仅做反弹
- 周线确认：日线 resample 周线，周线 MACD>0 + 日线 A/S → 满分

**3. 信号 metadata**
- signal_grade: C/B/A/S
- trend_filter: MA50 方向
- adx_value: 当前 ADX 值
- weekly_confirm: 周线是否确认
- entry_conditions: {macd_cross, rsi_ok, volume_ok, divergence}
- suggested_stop: 建议止损价（波段低点或 ATR 计算）
- exit_triggers: 当前触发的出场条件列表

**4. 三窗图表**
- 上窗（60%）：收盘价 + MA50 趋势线 + 买卖信号标记 + 背离标注
- 中窗（20%）：MACD 柱状图 + MACD 线 + 信号线 + 零轴
- 下窗（20%）：RSI 线 + 超买线(70) + 超卖线(30) + 50 中线

**5. 图例**
- 收盘价、MA50 趋势线、MACD 线、信号线、MACD 柱、RSI 线、超买/超卖参考线、买入/卖出信号点

## Key Assumptions to Validate
- [ ] ADX < 20 过滤确实能减少震荡市假信号（需回测验证）
- [ ] 周线 resample 的数据精度足够（相比直接获取周线数据）
- [ ] 三窗布局在 300px 高的弹窗中不会过于拥挤
- [ ] C 级信号大量出现时前端表格不会性能下降

## Not Doing (and Why)
- 实盘仓位计算和账户风险管理 — 仪表盘不连接交易账户
- 实时持仓追踪和动态止损移动 — 需要持久化持仓状态，超出扫描工具范围
- 盘中信号确认 vs 收盘价确认的双模式 — MVP 仅用收盘价（历史数据回看）
- 邮件/推送通知 — 后续独立功能

## Open Questions
- 周线数据是否应直接获取（而非 resample）？需要检查数据源是否支持周线
- C 级信号数量可能很大（每只股票每次 MACD 交叉都产生），是否需要前端分页或限制？
