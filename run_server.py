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
    from app import app, load_cached_data, background_refresh, _data_state
    import threading

    # 1. 先从缓存加载（秒级）
    print("\n正在加载缓存数据...")
    load_cached_data()
    print(f"✅ 缓存加载完成: {_data_state['total_stocks']} 只股票")
    if _data_state["error"]:
        print(f"⚠️  警告: {_data_state['error']}")

    # 2. 启动后台刷新线程
    refresh_thread = threading.Thread(target=background_refresh, daemon=True)
    refresh_thread.start()
    print("🔄 后台刷新最新数据中...")

    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
