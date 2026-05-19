#!/usr/bin/env python3
"""
布林带策略 Web 仪表盘 - 一键启动脚本
用法: python3 run_server.py
"""

import sys
import os
import webbrowser


def check_dependencies():
    """检查必要依赖"""
    missing = []
    try:
        import flask
    except ImportError:
        missing.append("flask>=3.0.0")

    try:
        import pandas
    except ImportError:
        missing.append("pandas>=2.0.0")

    try:
        import numpy
    except ImportError:
        missing.append("numpy>=1.24.0")

    if missing:
        print("=" * 60)
        print("❌ 缺少以下依赖:")
        for m in missing:
            print(f"   - {m}")
        print()
        print("请运行以下命令安装:")
        print(f"   pip install {' '.join(missing)}")
        print("=" * 60)
        sys.exit(1)


def main():
    check_dependencies()

    # 确保目录存在
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data/cache/bollinger", exist_ok=True)

    print("=" * 60)
    print("📊 布林带策略 Web 仪表盘")
    print("=" * 60)
    print("正在启动服务...")
    print()
    print(f"🌐 访问地址: http://localhost:5001")
    print()
    print("💡 提示:")
    print("   - 按 Ctrl+C 停止服务")
    print("   - 首次加载需要获取数据，请耐心等待")
    print("   - 后续访问使用缓存，速度很快")
    print("=" * 60)

    # 自动打开浏览器（可选）
    try:
        webbrowser.open("http://localhost:5001")
    except Exception:
        pass

    # 启动 Flask 应用
    from app import app, load_cached_data, load_data, _data_state

    # 1. 先从缓存加载（秒级，不访问网络）
    print("\n正在加载缓存数据...")
    load_cached_data()
    print(f"✅ 缓存加载完成: {_data_state['total_stocks']} 只股票")
    if _data_state["error"]:
        print(f"⚠️  警告: {_data_state['error']}")

    # 2. 启动定时更新任务
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: load_data(force_refresh=True),
        CronTrigger(day_of_week='mon-fri', hour=8, minute=0),
        id='full_refresh_0800',
        misfire_grace_time=300,
    )
    scheduler.add_job(
        lambda: load_data(groups=["A股", "ETF"]),
        CronTrigger(day_of_week='mon-fri', hour=14, minute=30),
        id='a_etf_update_1430',
        misfire_grace_time=300,
    )
    scheduler.add_job(
        lambda: load_data(groups=["港股"]),
        CronTrigger(day_of_week='mon-fri', hour=15, minute=30),
        id='hk_update_1530',
        misfire_grace_time=300,
    )
    scheduler.start()
    print("⏰ 定时任务已启动:")
    print("   工作日 08:00 - 全量更新")
    print("   工作日 14:30 - A股+ETF 更新")
    print("   工作日 15:30 - 港股更新")

    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
