# 定时数据更新

## Problem Statement

如何将 run_server 启动时的全量数据刷新替换为工作日分时段定向更新，减少不必要的网络请求，同时确保关键交易时段数据新鲜。

## Recommended Direction

**APScheduler + 分组过滤的 load_data**。

引入 APScheduler（BackgroundScheduler），配置三个工作日定时任务，在 `load_data()` 上增加可选的分组过滤和 force_refresh 参数。启动时仅加载缓存，不触发网络请求。

### 三个定时任务

| 时间 | Cron | 目标分组 | Force Refresh | 理由 |
|------|------|---------|---------------|------|
| 08:00 | `0 8 * * 1-5` | 全部 | 是 | A 股开盘前全量刷新，确保当日数据完整 |
| 14:30 | `30 14 * * 1-5` | A股 + ETF | 否 | A 股尾盘 30 分钟，增量拉取盘中数据 |
| 15:30 | `30 15 * * 1-5` | 港股 | 否 | A 股已收盘、港股尾盘 30 分钟，增量拉取 |

14:30 和 15:30 使用增量模式——已有缓存基础上仅拉取 `latest_date+1 天` 起的新数据，大幅减少请求量。

### 核心改动

**`app.py` — `load_data()` 签名扩展**：

```python
def load_data(groups: List[str] | None = None, force_refresh: bool = False):
```

- `groups=None` → 全部股票（保持向后兼容，手动刷新按钮不变）
- `groups=["A股", "ETF"]` → 仅处理指定分组
- `force_refresh=True` → 传递到 `fetch_batch_data()`，跳过增量逻辑

分组过滤发生在 `load_watchlist()` 之后、`fetch_batch_data()` 之前——在内存中过滤 `stocks` 列表。

**`run_server.py` — 调度器初始化**：

```python
from apscheduler.schedulers.background import BackgroundScheduler

# 替换原来的 background_refresh 线程
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: load_data(force_refresh=True), CronTrigger(day_of_week='mon-fri', hour=8, minute=0))
scheduler.add_job(lambda: load_data(groups=["A股", "ETF"]), CronTrigger(day_of_week='mon-fri', hour=14, minute=30))
scheduler.add_job(lambda: load_data(groups=["港股"]), CronTrigger(day_of_week='mon-fri', hour=15, minute=30))
scheduler.start()
```

删除 `background_refresh` 线程启动代码。

### 文件变更清单

| 文件 | 改动 |
|------|------|
| `requirements.txt` | 新增 `apscheduler` |
| `run_server.py` | 删除 `background_refresh` 线程；新增 APScheduler 初始化（3 个 job） |
| `app.py` | `load_data()` 新增 `groups` 和 `force_refresh` 参数；`fetch_batch_data()` 调用时传入 `force_refresh` |

## Key Assumptions

- [ ] APScheduler BackgroundScheduler 在 Flask 非 debug 模式下正常工作（Flask + APScheduler 是成熟组合）
- [ ] 分组更新时其他分组的 `data_dict` 条目保持不变——需要合并而非替换（验证方式：更新 A 股后，港股数据仍可正常展示）
- [ ] 14:30 时 A 股当日数据已可通过 AKShare 获取（盘中数据源支持）
- [ ] 周一至周五判断足够——不处理法定假日，节假日的无效请求会被 AKShare fallback 到样本数据

## MVP Scope

**In scope:**
- 三个 APScheduler 定时任务（08:00 / 14:30 / 15:30，仅工作日）
- `load_data()` 支持分组过滤和 force_refresh
- 启动时仅加载缓存、不访问网络
- 手动刷新按钮保持不变（全量 force_refresh）

**Out of scope:**
- 法定假日精确跳过
- 定时任务失败重试机制（APScheduler 默认 misfire 策略已足够）
- 前端展示"下次更新时间"
- WebSocket 实时推送

## Not Doing (and Why)

- **法定假日检测** — 复杂度远超收益。非交易日请求会 fallback 到缓存或样本数据，无副作用
- **失败重试队列** — 首次实现保持简单，APScheduler 的 misfire_grace_time 已提供基础容错
- **WebSocket 推送更新完成通知** — 当前前端 3 秒轮询 `loading` 状态已能满足需求
- **定时任务启用/禁用开关** — 暂无需求，可通过注释 cron job 行手动控制
- **将调度器抽到独立模块 `src/scheduler.py`** — 三个 job 的配置不到 15 行，独立文件是过度抽象

## Open Questions

- 无
