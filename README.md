# 布林带策略工作台

一个专业的 A 股量化交易策略工作台，支持多标的布林带策略回测、信号扫描和可视化分析。

## 特性

- **多数据源支持**：AKShare v1/v2 → BaoStock → 本地样本数据的自动 fallback 机制
- **智能缓存**：数据和计算结果分层缓存，加速重复运行
- **布林带策略**：经典的 N=20, M=2 布林带策略，支持自定义参数
- **成交量增强**：信号质量通过成交量放大确认
- **HTML 仪表板**：JavaScript 驱动的交互式展示，从缓存加载数据
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
# 运行自选股扫描和信号生成
python run_workbench.py
```

### 查看结果

```bash
# 启动本地服务器
python -m http.server 8000
```

然后浏览器访问：http://localhost:8000/logs/dashboard.html

## 项目结构

```
.
├── run_workbench.py      # 多标的扫描主入口
├── run_backtest.py       # 单标的回测入口
├── watchlist.csv         # 自选股配置
├── requirements.txt      # 项目依赖
├── src/
│   ├── config.py         # 全局配置管理
│   ├── data_fetcher.py   # 多源数据获取和缓存
│   ├── bollinger.py      # 布林带计算
│   ├── signals.py        # 信号生成和扫描
│   ├── cache.py          # 结果缓存模块
│   ├── backtest.py       # 回测引擎
│   └── output.py         # HTML 和报告生成
├── data/
│   ├── cache/            # 计算结果缓存
│   │   ├── metadata.json
│   │   ├── signals.csv
│   │   └── bollinger/
│   └── *.csv             # 原始数据缓存
└── logs/
    ├── dashboard.html    # 新 JS 驱动的仪表板
    └── dashboard_old.html # 旧版 Python 渲染仪表板
```

## 策略逻辑

### 布林带参数

- 中轨：20 日均线（MA20）
- 上轨：MA20 + 2 * 标准差（SD）
- 下轨：MA20 - 2 * 标准差

### 信号生成

- **买入信号**：收盘价跌破下轨
- **卖出信号**：收盘价突破上轨

### 成交量增强

- **普通信号**：满足上述布林带条件
- **增强信号**：布林带条件 + 成交量 > 1.5 倍 20 日均量

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
- ⏳ 自适应参数优化
- ⏳ Streamlit Web 仪表盘
- ⏳ 完整交易日志分析

## 常见问题

### Q: 为什么需要本地服务器打开 HTML？

A: 浏览器安全策略限制了直接通过 file:// 协议读取本地 CSV 文件。使用 Python 简单服务器可以解决跨域问题。

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
