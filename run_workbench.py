#!/usr/bin/env python
"""
布林带策略工作台 - 主入口
一键运行：自选股扫描 -> 信号检测 -> HTML 仪表板生成
"""

import sys
import os

# 添加当前目录到路径，方便导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_config, ensure_dirs
from src.watchlist import load_watchlist, create_sample_watchlist
from src.data_fetcher import fetch_batch_data
from src.bollinger import calculate_bollinger
from src.signals import scan_all_signals
from src.output import generate_dashboard_html, generate_dashboard_js
from src import cache
from datetime import datetime


def main():
    """主流程"""
    print("="*60)
    print("📊 布林带策略工作台")
    print("="*60)

    # 1. 初始化配置
    config = get_config()
    ensure_dirs()

    # 2. 加载自选股
    print("\n📋 加载自选股...")
    watchlist_file = "watchlist.csv"
    if not os.path.exists(watchlist_file):
        print(f"⚠️  自选股文件不存在，创建示例...")
        create_sample_watchlist(watchlist_file)

    try:
        stocks = load_watchlist(watchlist_file)
        print(f"✅ 成功加载 {len(stocks)} 只股票")
    except Exception as e:
        print(f"❌ 加载自选股失败: {e}")
        return

    if len(stocks) == 0:
        print("❌ 自选股为空")
        return

    # 3. 批量获取数据
    print("\n📥 批量获取数据...")
    try:
        data_dict_raw, failed = fetch_batch_data(
            stocks=stocks,
            period=config.period,
            start_date=config.start_date,
            use_cache=True,
            request_interval=0.5
        )
    except Exception as e:
        print(f"❌ 批量获取数据失败: {e}")
        return

    # 4. 对每只股票计算布林带
    print("\n🔧 计算布林带...")
    data_dict_full = {}  # {symbol: (name, df_with_bollinger)}
    for stock in stocks:
        symbol = stock.symbol
        name = stock.name
        if symbol not in data_dict_raw:
            continue

        df = data_dict_raw[symbol]
        df = calculate_bollinger(df, n=config.bollinger_n, m=config.bollinger_m)
        data_dict_full[symbol] = (name, df)

        # 保存布林带历史缓存
        cache.save_bollinger_history(symbol, name, df)

    print(f"✅ 完成 {len(data_dict_full)} 只股票的布林带计算")

    # 5. 扫描信号
    print("\n🔍 扫描信号...")
    volume_threshold = 1.5  # 成交量放大阈值（1.5倍）
    volume_window = 20

    # 转换格式给 scan_all_signals
    signals = scan_all_signals(
        data_dict=data_dict_full,
        volume_threshold=volume_threshold,
        volume_window=volume_window
    )

    buy_count = len([s for s in signals if s.signal_type == "BUY"])
    sell_count = len([s for s in signals if s.signal_type == "SELL"])
    enhanced_count = len([s for s in signals if s.is_enhanced])

    print(f"✅ 发现信号: 买入 {buy_count}, 卖出 {sell_count}, 增强 {enhanced_count}")

    # 5. 保存缓存
    print("\n💾 保存缓存数据...")
    scan_time = datetime.now()
    cache.save_signals(signals)
    cache.save_metadata(
        config=config,
        scan_time=scan_time,
        buy_count=buy_count,
        sell_count=sell_count,
        enhanced_count=enhanced_count,
        total_stocks=len(data_dict_full)
    )
    print(f"✅ 缓存已保存到 {config.cache_base_dir}/")

    # 6. 生成 HTML 仪表板
    print("\n📄 生成仪表板...")
    dashboard_path = os.path.join(config.log_dir, "dashboard.html")
    dashboard_new_path = os.path.join(config.log_dir, "dashboard_new.html")
    try:
        # 生成旧版本（完整功能，包含全部概览）
        generate_dashboard_html(
            signals=signals,
            data_dict=data_dict_full,
            output_path=dashboard_path,
            volume_threshold=volume_threshold
        )
        # 同时保留新版本用于对比
        generate_dashboard_js(output_path=dashboard_new_path)
    except Exception as e:
        print(f"❌ 生成仪表板失败: {e}")
        return

    # 7. 打印总结
    print("\n" + "="*60)
    print("✅ 扫描完成！")
    print("="*60)
    print(f"📊 扫描股票数: {len(data_dict_full)}")
    print(f"📈 买入信号: {buy_count}")
    print(f"📉 卖出信号: {sell_count}")
    print(f"🟢 增强信号: {enhanced_count}")
    print(f"\n📄 主仪表板 (完整功能): {os.path.abspath(dashboard_path)}")
    print(f"📄 新仪表板 (JS 驱动): {os.path.abspath(dashboard_new_path)}")
    print(f"💾 缓存数据: {os.path.abspath(config.cache_base_dir)}/")
    print("\n💡 提示: 新仪表板使用 JS 加载缓存数据，")
    print("   如果直接打开 HTML 遇到跨域问题，请使用本地服务器:")
    print("   python -m http.server 8000")
    print("   然后访问: http://localhost:8000/logs/dashboard.html")
    print("="*60)


if __name__ == "__main__":
    main()
