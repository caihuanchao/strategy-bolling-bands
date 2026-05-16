---
## 布林带Web仪表板实施计划

## Problem Statement

我们如何在新版本的JS驱动仪表板中实现"全部概览"功能，同时为未来提供更好的扩展性？

## Recommended Direction

构建一个轻量级的Flask Web应用，复用现有的数据获取和计算逻辑，通过API提供数据，前端用现代方式调用。

## 架构：
浏览器 → Flask服务 → 现有的src模块 → 缓存数据

## 为什么选择这个方向：
- 保留现有代码的全部价值
- 提供真正的交互式体验
- 为未来功能扩展打好基础
- 对个人使用来说复杂度适中

## Key Assumptions to Validate

- 用户愿意每次启动服务（已确认）
- 用户接受安装新依赖（已确认）
- 性能可以接受（首次加载后会很快）
- 用户会实际使用新增的交互功能

## MVP Scope
包含：

1. Flask应用 (app.py) - 简单的Web服务
2. API路由：
    - / - 首页
    - /api/signals - 获取信号数据
    - /api/stocks - 获取全部股票概览
    - /api/stock/<symbol> - 获取单只股票详情
3. 模板渲染 - 复用现有HTML结构
4. 启动脚本 - python run_server.py一键启动

## 复用现有代码（无需重写）：

- src/config.py - 配置管理
- src/watchlist.py - 自选股加载
- src/data_fetcher.py - 数据获取
- src/bollinger.py - 布林带计算
- src/signals.py - 信号扫描
- src/cache.py - 缓存管理

## Not Doing (and Why)

- 用户认证 - 个人使用，不需要
- 数据库（SQLite） - 先用文件缓存，需要时再加
- 实时行情推送 - 用定时刷新或手动刷新足够
- 部署到云端 - 本地运行就行
- 历史回测功能 - 那是Phase 1/2的职责，保持独立
- Docker容器化 - 个人使用不需要

## Implementation Steps

### Step 1: 创建Flask应用骨架 (app.py)

- 初始化Flask应用
- 创建内存数据存储结构
- 实现load_data()函数来加载和计算数据
- 连接现有的src/模块

### Step 2: API端点实现

- /api/signals - 返回买入/卖出信号
- /api/stocks - 返回全部股票概览（带布林带位置）
- /api/stock/<symbol> - 返回单只股票的完整数据和历史
- /api/refresh - 手动触发数据刷新

### Step 3: 前端模板重构

- 创建templates/目录
- 把现有HTML改成Jinja2模板
- 保留Tab切换功能
- 用JavaScript调用API而不是加载静态文件

### Step 4: 创建启动脚本 (run_server.py)

- 检查Flask依赖
- 自动创建目录结构
- 启动Flask开发服务器
- 自动打开浏览器

### Step 5: 测试验证

- 运行python run_server.py
- 测试"今日信号"Tab
- 测试"全部概览"Tab
- 测试点击查看详情功能

## Open Questions

1. 默认端口用5000还是8000？ 建议5000（Flask默认）
2. 是否保留旧的run_workbench.py？ 建议保留作为备选方案
3. 是否需要"刷新数据"按钮？ 建议加入，方便手动刷新

## Files to Create/Modify
新建文件：

- app.py - Flask主应用
- run_server.py - 启动脚本
- templates/dashboard.html - Jinja2模板
- requirements.txt - Python依赖

## 不修改现有文件：

- src/目录下所有模块保持不变
- run_workbench.py保留作为备选

## Success Criteria

- python run_server.py可以一键启动
- 浏览器自动打开http://localhost:5000
- "今日信号"Tab正常显示
- "全部概览"Tab显示所有股票状态
- 点击股票可以查看详情
- 刷新数据功能正常工作

---
