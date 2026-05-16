# 量化策略工作台

一个专业的多策略量化交易工作台，内置五大策略（布林带触碰、双均线交叉、成交量分析、三重确认、KDJ+布林带+ATR），支持信号扫描、回测和交互式可视化分析。

## 特性

- **多策略支持**：内置五大策略，通过策略注册中心统一管理，支持一键切换
- **策略感知渲染**：前端根据当前策略动态适配——个股详情页展示对应维度的专属分析卡片和三面板图表
- **多数据源支持**：AKShare v1/v2 → BaoStock → 本地样本数据的自动 fallback 机制
- **智能缓存**：数据和计算结果分层缓存，加速重复运行
- **布林带触碰策略**：经典的 N=20, M=2 布林带策略，触轨回归，支持自定义参数
- **双均线交叉策略**：EMA 快慢线金叉/死叉 + 成交量确认 + 可靠性四星评级
- **成交量分析策略**：OBV 背离检测 + 放量突破识别 + 缩量回调确认 + K 线形态评分
- **三重确认策略**：MACD + RSI + 成交量 + ADX 四指标共振，C/B/A/S 四级信号分级
- **KDJ+布林带+ATR 策略**：震荡/趋势/蓄势三环境感知系统，KDJ 动量检测 + 布林带位置 + ATR 动态止损
- **HTML 仪表板**：静态 HTML 展示（旧版保留）
- **Flask Web 仪表盘**：一键启动的交互式 Web 应用，支持实时查看信号、全部概览、股票详情和手动刷新
- **参数实验室**：策略专属预设模板 + 参数滑块微调 + 信号变化预览 + 一键应用重算
- **技术指标深度解读**：双层解读体系——通用层（MACD/RSI/布林带）+ 策略专属层（5 套解读器），每维度输出 summary/detail/checklist 标准结构
- **多标的支持**：通过 watchlist.csv 管理自选股
- **完整回测**：收益率、CAGR、最大回撤、胜率、盈亏比等指标
- **导出友好**：CSV 格式的信号和历史数据，可用 Excel 直接分析

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置自选股

编辑 `watchlist.csv`，格式如下：

```csv
symbol,name
000333,美的集团
000001,平安银行
600519,贵州茅台
```

### 运行工作流

```bash
# 启动 Web 仪表盘（推荐，一键交互式访问）
python run_server.py

# 运行自选股扫描和静态 HTML 生成
python run_workbench.py
```

### 查看结果

运行 `python run_server.py` 后，浏览器会自动打开 http://localhost:5001

或运行静态版本：

```bash
python run_workbench.py
python -m http.server 8000
# 访问 http://localhost:8000/logs/dashboard.html
```

## 项目结构

```
.
├── run_server.py         # Web 仪表盘一键启动（推荐）
├── app.py                # Flask Web 应用
├── run_workbench.py      # 多标的扫描 + 静态 HTML 生成
├── run_backtest.py       # 单标的回测入口
├── templates/
│   └── dashboard.html    # Jinja2 仪表盘模板
├── watchlist.csv         # 自选股配置
├── requirements.txt      # 项目依赖
├── src/
│   ├── config.py                  # 全局配置管理
│   ├── watchlist.py               # 自选股加载
│   ├── data_fetcher.py            # 多源数据获取和缓存
│   ├── bollinger.py               # 布林带计算
│   ├── indicators.py              # MACD/RSI 指标计算
│   ├── indicator_interpreter.py   # 技术指标结构化解读
│   ├── signals.py                 # 信号生成和扫描
│   ├── strategies/                # 策略系统（注册中心 + 各策略实现）
│   │   ├── __init__.py                        # StrategyBase ABC + StrategyRegistry
│   │   ├── bollinger.py                       # BollingerStrategy
│   │   ├── dual_ma.py                         # DualMAStrategy
│   │   ├── dual_ma_interpreter.py             # 双均线策略结构化解读
│   │   ├── volume.py                          # VolumeAnalysisStrategy
│   │   ├── volume_interpreter.py              # 成交量分析策略结构化解读
│   │   ├── triple_confirm.py                  # TripleConfirmStrategy
│   │   ├── triple_confirm_interpreter.py      # 三重确认策略结构化解读
│   │   ├── kdj_bollinger_atr.py               # KdjBollingerAtrStrategy
│   │   └── kdj_bollinger_atr_interpreter.py   # KDJ+BB+ATR 策略结构化解读
│   ├── multi_period.py            # 多周期共振逻辑
│   ├── cache.py                   # 结果缓存模块
│   ├── backtest.py                # 回测引擎
│   └── output.py                  # HTML 和报告生成
├── data/
│   ├── cache/            # 计算结果缓存
│   │   ├── metadata.json
│   │   ├── signals.csv
│   │   └── bollinger/
│   └── *.csv             # 原始数据缓存
└── logs/
    ├── dashboard.html    # 静态仪表板
    └── dashboard_old.html # 旧版 Python 渲染仪表板
```

## 策略逻辑

### 布林带触碰策略

**参数：** 中轨 MA20，上轨 MA20 + 2×SD，下轨 MA20 - 2×SD。

- **买入信号**：收盘价跌破下轨 → 超跌反弹预期
- **卖出信号**：收盘价突破上轨 → 高位回调预期
- **增强信号**：上述条件 + 成交量 > 1.5 倍 20 日均量（成交量确认）

### 双均线交叉策略

- 快线：EMA(5)，默认周期 5
- 慢线：EMA(20)，默认周期 20
- 量比阈值：1.2x，默认值

**信号生成：**

- **买入信号（金叉）**：快线上穿慢线 + 成交量 ≥ 量比阈值
- **卖出信号（死叉）**：快线下穿慢线 + 成交量 ≥ 量比阈值

**策略专属解读（个股详情页）：** 当切换到双均线策略后，个股详情页展示：
- 交叉信号判定（金叉/死叉状态）
- 趋势判定（多头/空头排列，EMA 斜率方向）
- 信号可靠性评级（弱势/标准/强势/金叉死叉，含星级）
- 成交量配合分析（放量/缩量确认）
- 综合操作建议（入场/出场/止损）

### 成交量分析策略

基于 OBV（能量潮）+ 量价关系 + K 线形态的综合成交量分析策略，固定参数。

**核心指标：**

- OBV 背离检测：顶背离（价格新高+OBV 未新高）/ 底背离（价格新低+OBV 未新低），回溯窗口 20 日
- 放量突破：成交量 ≥ 1.5 倍 20 日均量 + 价格突破布林带中轨
- 缩量回调：成交量 ≤ 0.5 倍 20 日均量 + 价格回踩中轨企稳
- 形态评分：识别成交量放量/缩量组合形态（如放量+缩量回调+再放量），评分 0-5 分
- 高潮识别：极端放量（量比 > 3x）后缩量 < 0.5x = 底部高潮；放量 > 2.5x + 长上影 = 顶部高潮

**信号等级：** 综合 OBV、突破、回调、形态四个维度打分，≥3 分生成买入/卖出信号。

**策略专属解读：** 7 维解读（量价关系 / 背离 / 放量突破 / 缩量回调 / OBV / 形态识别 / 操作建议）。

### 三重确认策略

基于 MACD + RSI + 成交量 + ADX 四指标共振的确认型策略，固定参数，C/B/A/S 四级信号分级。

**确认维度：**

| 维度 | 做多条件 | 做空条件 |
|------|----------|----------|
| MACD | 金叉或金叉区域 + 柱状图放大 | 死叉或死叉区域 + 柱状图放大 |
| RSI | 30-65 区间（非超卖区抄底，非超买区追高） | 45-70 区间 |
| 成交量 | 量比 ≥ 1.0x（A 级）/ ≥ 1.5x（S 级） | 同左 |
| 辅助（ADX+MA50） | ADX > 20（趋势市），MA50 方向过滤 | 同左 |

**信号分级：**

| 等级 | 条件 | 可靠性 | 操作 |
|------|------|--------|------|
| **S** | 4 维确认 + 量比 ≥ 1.5x | ~70-75% | 重仓 |
| **A** | 3 维确认（MACD+RSI+量比 ≥ 1.0x） | ~60-65% | 标准仓位 |
| **B** | 2 维确认（MACD+RSI） | ~50-55% | 轻仓试探 |
| **C** | 单一指标确认 | ~40-45% | 仅观察 |

**策略专属解读：** 7 维解读（信号等级 / MACD 确认 / RSI 确认 / 成交量确认 / 辅助指标 / 出场触发 / 操作建议）。

### KDJ+布林带+ATR 策略

核心差异化在于**环境感知**——先判定市场处于震荡/趋势/蓄势，再切换对应交易模式。

**三环境系统：**

| 环境 | 判定条件 | 交易模式 |
|------|----------|----------|
| 震荡 | 中轨斜率 ≈ 0 + 带宽非极窄 + ATR 稳定 | 区间回归：触上轨做空，触下轨做多，目标中轨 |
| 趋势 | 中轨斜率 > 阈值 + 带宽扩大 + ATR 上升 | 顺势回调：只做顺势方向，回调到中轨入场 |
| 蓄势 | 带宽 6 月最低 + ATR 低位 + 中轨走平 | 突破跟进：等待突破 K 线收盘确认后入场 |

**核心指标：**

- KDJ(9,3,3)：RSV → K/D 递推平滑，J = 3K - 2D（放大器），检测金叉/死叉/背离
- 布林带(20,2)：触轨、穿刺回归、沿轨爬行、Squeeze 收缩检测
- ATR(14)：波动率环境判定 + 动态止损距离（震荡 1.5×ATR / 趋势 2×ATR）
- 周线布林带中轨方向过滤：中轨向上只做多，向下只做空

**信号分级：** 环境感知的 C/B/A/S 四级，S 级需 Squeeze 突破 + KDJ 背离 + 量比 ≥ 1.3x + ATR 扩张。

**策略专属解读：** 7 维解读（环境 / 信号等级 / KDJ 维度 / 布林带维度 / ATR 维度 / 出场条件 / 交易建议），含 ATR 动态止损价格。

### 策略系统架构

```
策略注册中心 (StrategyRegistry)
    ├── BollingerStrategy  (布林带触碰)
    │   ├── 参数: {n: 20, m: 2.0}
    │   └── 4 组预设: 趋势跟踪/震荡市/高波动/收紧
    ├── DualMAStrategy  (双均线交叉)
    │   ├── 参数: {fast_period: 5, slow_period: 20, volume_threshold: 1.2}
    │   └── 3 组预设: 标准/敏感/滞后
    ├── VolumeAnalysisStrategy  (成交量分析)
    │   ├── 参数: 固定（divergence_lookback=20, volume_ratio_threshold=1.5 等）
    │   └── 1 组预设: 标准
    ├── TripleConfirmStrategy  (三重确认)
    │   ├── 参数: 固定（MACD+RSI+成交量+ADX 阈值）
    │   └── 1 组预设: 标准
    └── KdjBollingerAtrStrategy  (KDJ+布林带+ATR)
        ├── 参数: 固定（KDJ 9,3,3; ATR 14; BB 20,2）
        └── 1 组预设: 标准经典参数
```

策略切换通过 API `/api/strategy/switch` 完成，后台自动重算全量信号，前端轮询等待完成后刷新。

### 技术指标深度解读

解读系统采用**双层架构**，在个股详情 API (`/api/stock/{symbol}`) 中组合输出。每套解读器返回多维度 dict，每个维度均包含 `{summary, detail, checklist, [专属字段]}` 的标准结构。

```
DataFrame (含各策略计算结果)
    │
    ├──→ interpret_all(latest, prev)         ← 通用层，始终执行
    │     └── MACD / RSI / 布林带 三维解读
    │
    └──→ interpret_xxx_all(df)               ← 策略专属层，按需执行 (5 套)
          ├── interpret_dual_ma_all()          (双均线)
          ├── interpret_volume_all()           (成交量分析)
          ├── interpret_triple_confirm_all()   (三重确认)
          └── interpret_kdj_bb_atr_all()       (KDJ+BB+ATR)
```

#### 通用层 (`src/indicator_interpreter.py`)

`interpret_all(latest, prev)` 始终运行，对 MACD/RSI/布林带三个经典指标逐维度判定并生成中文解读：

| 维度 | 函数 | 判定逻辑 |
|------|------|----------|
| **MACD** | `interpret_macd()` | DIF/DEA 零轴位置 → 快慢线关系（金叉/死叉/粘合） → 柱状图动能分析 → 状态组合生成 summary + checklist |
| **RSI** | `interpret_rsi()` | 六区判定（严重超买≥80 / 超买 70-80 / 偏强 50-70 / 偏弱 30-50 / 超卖 20-30 / 严重超卖 <20） → 较前一周期趋势方向 |
| **布林带** | `interpret_bollinger()` | 价格位置（上轨/中上/中下/下轨） → %B 归一化 → 带宽分析（宽/正常/收窄） |

#### 策略专属层

app.py 通过检测 DataFrame 中是否存在策略专属列来调度解读器——**不依赖当前活跃策略**，即一次请求可同时生成多套解读：

| 策略解读器 | 源文件 | 触发条件 | 维度数 |
|-----------|--------|----------|--------|
| 双均线 | `src/strategies/dual_ma_interpreter.py` | 存在 `ema_fast`, `ema_slow` 列 | 5 维 |
| 成交量分析 | `src/strategies/volume_interpreter.py` | 存在 `obv`, `volume_ratio` 列 | 7 维 |
| 三重确认 | `src/strategies/triple_confirm_interpreter.py` | 存在 `macd`, `adx` 列 | 7 维 |
| KDJ+BB+ATR | `src/strategies/kdj_bollinger_atr_interpreter.py` | 存在 `kdj_k`, `atr` 列 | 7 维 |

**以 KDJ+布林带+ATR 为例，7 维解读：**

| 维度 | 内容 |
|------|------|
| `environment` | 震荡/趋势/蓄势三模式判定 + 中轨斜率 + ATR 趋势 + 周线确认 |
| `signal_grade` | C/B/A/S 四级信号分级 + 可靠性说明 + 仓位建议 |
| `kdj_dimension` | K/D/J 数值 + 超买超卖区域 + J 值诊断 + 金叉死叉 + 背离检测 |
| `bollinger_dimension` | 价格位置（触轨/穿刺/爬行/Squeeze） + 带宽状态 + 中轨斜率 |
| `atr_dimension` | ATR 数值 + 波动率趋势 + 动态止损价格计算 |
| `exit_triggers` | 5 个出场条件检测（中轨回归/KDJ 反转/J 回落/ATR 跳升/跌破 MA20） |
| `trading_advice` | 综合入场建议 + KDJ 钝化警告 + 环境特定目标位 |

**以双均线为例，5 维解读：**

| 维度 | 内容 |
|------|------|
| `cross_signal` | 金叉/死叉/粘合状态 + 最近一次交叉距今天数 |
| `trend` | 多头/空头排列 + EMA 斜率方向 + 价格与均线关系 |
| `reliability` | 四星制评级（★★★★☆）——基于交叉确认、均线方向、价格位置、成交量 4 项条件 |
| `volume` | 量比分级（显著放量/温和/轻微/缩量）+ 成交量趋势 |
| `trading_advice` | 入场建议 + 出场建议 + 止损位计算 |

**前端渲染**：`dashboard.html` 中的 `renderInterpretation()` 按当前活跃策略选择对应的卡片组，如 KDJ+BB+ATR 策略展示 7 张解读卡片（环境/信号等级/KDJ/布林带/ATR/出场/建议）。

## 使用指南

### 单标的回测

```python
# 编辑 src/config.py 修改配置
python run_backtest.py
```

### 修改策略参数

编辑 `src/config.py`：

```python
@dataclass
class Config:
    symbol: str = "000333"
    symbol_name: str = "美的集团"
    bollinger_n: int = 20       # MA 周期
    bollinger_m: float = 2.0     # 标准差倍数
    # ...
```

### 参数实验室

Web 仪表盘中的「参数实验室」Tab 允许在不修改代码的情况下切换布林带参数并预览效果：

**预设模板：**

| 预设 | N (周期) | M (倍数) | 适用场景 |
|------|----------|----------|----------|
| 趋势跟踪 | 20 | 2.0 | 标准参数，适合趋势行情 |
| 震荡市 | 10 | 1.5 | 短周期窄带，适合震荡行情 |
| 高波动 | 30 | 2.5 | 长周期宽带，适合高波动行情 |
| 收紧 | 15 | 1.8 | 中短周期，提前捕捉变盘 |

**操作流程：**
1. 点击「参数实验室」Tab
2. 查看「当前市场特征速览」面板快速了解市场状态
3. 选择预设模板，或手动拖动 N/M 滑块微调
4. 观察「信号变化对比」面板中的预览差异
5. 点击「应用参数」触发全量信号重算

参数仅存在于内存中，刷新页面或点击「刷新数据」按钮即恢复默认 (20, 2.0)。

#### 当前市场特征速览：指标计算方式

三个指标通过遍历全市场所有股票最新行情即时计算（只读内存，秒级完成）：

**平均带宽：**

```
带宽 = (boll_up - boll_down) / ma_mid
平均带宽 = 所有股票最新带宽的算术平均
```

- `boll_up` = 布林带上轨，`boll_down` = 布林带下轨，`ma_mid` = 中轨（MA20）
- 带宽表示布林带宽度相对于股价的比例。例如 20% 意味着通道宽度约为股价的 20%
- 带宽越宽 → 市场波动越剧烈；越窄 → 盘整蓄力，接近变盘
- 源数据列：`boll_up`, `boll_down`, `ma_mid`（由 `src/bollinger.py` 的 `calculate_bollinger()` 计算）

**平均标准差：**

```
平均标准差 = 所有股票最近 5 个交易日 std 均值的算术平均
```

- `std` = 20 日滚动标准差（收盘价对 MA20 的偏离程度）
- 取每只股票 DataFrame 中 `std` 列最近 5 行的均值，再对所有股票求平均
- 直接反映市场价格波动幅度——数值越大，价格摆动越剧烈
- 源数据列：`std`（由 `src/bollinger.py` 的 `calculate_bollinger()` 计算，`df["close"].rolling(20).std()`）

**波动率趋势：**

```
recent_avg = 最近 5 期 std 的均值
older_avg  = 前 15 期 std 的均值（窗口共 20 期）
变化率 = (recent_avg - older_avg) / older_avg

若 变化率 > +5%  → 上升 ↑（波动率扩张）
若 变化率 < -5%  → 下降 ↓（波动率收敛）
否则            → 平稳（波动率稳定）
```

- 对比近期（5 期）与稍远期（前 15 期）的标准差，判断波动率是在加速还是收敛
- ±5% 阈值用于过滤日常微小波动，只报告有意义的方向变化
- 上升 → 市场波动增大，可参考「高波动」预设；下降 → 趋于平静，可关注变盘机会

**边界处理：**
- 任何股票的 `boll_up`/`boll_mid`/`boll_down` 为 NaN 或 `boll_mid ≤ 0` 时，该股票不参与带宽计算
- DataFrame 行数不足 5 时，该股票不参与标准差计算
- `data_dict` 为空（数据未加载）时，三个指标均显示"数据未就绪"

### 数据缓存机制

第一次运行后，数据和计算结果会缓存在：

- `data/*.csv`：原始 OHLCV 数据
- `data/cache/`：计算结果（元数据、信号、布林带历史）

第二次运行会从缓存加载，大幅加速！

## 输出说明

运行 `run_workbench.py` 后生成以下文件：

### 缓存数据（data/cache/）

- `metadata.json`：扫描信息、策略参数、信号统计
- `signals.csv`：发现的信号列表
- `bollinger/{symbol}.csv`：每只股票的完整布林带历史

### HTML 仪表板（logs/）

- `dashboard.html`：新 JS 驱动的交互式仪表板
- `dashboard_old.html`：旧版 Python 渲染仪表板（用于对比）

### 控制台输出

- 扫描股票数、买入/卖出信号数
- 增强信号统计
- 文件路径提示

## 路线图

### Phase 1 (MVP)
- ✅ 日线级别布林带策略
- ✅ 基础回测引擎
- ✅ 多标的扫描支持
- ✅ CSV 结果缓存
- ✅ JavaScript 驱动的 HTML 仪表板

### Phase 2
- ✅ 多周期共振（4小时/1小时）
- ✅ MACD/RSI 辅助指标
- ⏳ 信号历史对比


### Phase 2 使用

```bash
# 运行多周期共振回测
python run_backtest.py --phase2

# 运行单周期基准回测（对比用）
python run_backtest.py
```

Phase 2 新增模块：
- `src/indicators.py`：MACD、RSI 指标计算
- `src/multi_period.py`：多周期数据对齐、共振信号检查
- 扩展配置、回测、输出模块支持多周期模式

### Phase 3
- ✅ Flask Web 仪表盘（替代原计划的 Streamlit）
- ✅ 自适应参数优化（参数实验室）
- ✅ 技术指标深度解读（MACD/RSI/布林带结构化分析）
- ✅ 多策略系统（五大策略：布林带触碰 + 双均线交叉 + 成交量分析 + 三重确认 + KDJ+BB+ATR，策略注册中心 + 一键切换）
- ✅ 策略感知渲染（个股详情页根据策略动态展示专属分析）
- ⏳ 完整交易日志分析

## 常见问题

### Q: 为什么推荐使用 Web 仪表盘而不是直接打开 HTML？

A: `run_server.py` 启动的 Flask 应用提供实时数据交互、股票详情查看和手动刷新功能，体验优于静态 HTML。如果不需要 Web 服务，仍可使用 `run_workbench.py` 生成静态 HTML 并通过 `python -m http.server` 查看。

### Q: 数据缓存有效期是多久？

A: 目前是永久缓存。如需重新下载数据，删除 `data/` 目录下对应的 CSV 文件即可。

### Q: 如何添加新的数据源？

A: 参考 `src/data_fetcher.py` 中的现有代码，添加新的数据源 fallback 函数。

### Q: 为什么有时候会使用样本数据？

A: 当所有在线数据源都失败时，系统会使用本地生成的随机样本数据（Seed=42），这可以保证程序在网络问题时仍能运行演示。

## 技术栈

- **数据分析**：Pandas, NumPy
- **数据获取**：AKShare, BaoStock
- **可视化**：Matplotlib, HTML/CSS/JavaScript
- **缓存策略**：CSV + JSON 分层缓存

## 项目说明

这是一个教学项目，用于学习和演示量化交易策略的开发方法。**不构成任何投资建议**。股市有风险，投资需谨慎。

## License

MIT License

## Contributing

欢迎提交 Issue 和 PR！
