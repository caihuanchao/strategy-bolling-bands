#!/usr/bin/env python
"""
自适应多周期布林带交易工作台 - 主入口
支持 Phase 1 (单周期) 和 Phase 2 (多周期共振)
"""

import sys
import argparse

from src.config import get_config, ensure_dirs


def main_phase1():
    """Phase 1: 单周期回测（保持原有功能）"""
    from src.data_fetcher import get_stock_data
    from src.bollinger import calculate_bollinger
    from src.signals import generate_signals
    from src.backtest import run_backtest
    from src.output import save_backtest_report

    print("=" * 60)
    print("自适应多周期布林带交易工作台 - Phase 1 (单周期)")
    print("=" * 60)

    config = get_config()
    ensure_dirs()
    print(f"标的: {config.symbol_name}({config.symbol})")
    print(f"布林带参数: N={config.bollinger_n}, M={config.bollinger_m}")
    print(f"初始资金: ¥{config.initial_capital:,.2f}")

    df = get_stock_data()
    df = calculate_bollinger(df)
    df = generate_signals(df)

    print("\n运行回测...")
    result = run_backtest(df)

    save_backtest_report(result)

    print("\n最后20天数据预览:")
    cols = ["date", "close", "ma_mid", "boll_up", "boll_down", "buy_signal", "sell_signal", "portfolio_value"]
    print(result.df.tail(20)[cols].to_string(index=False))


def main_phase2():
    """Phase 2: 多周期共振回测"""
    from src.backtest import run_multi_period_backtest
    from src.output import save_multi_period_report, print_performance_report

    print("=" * 60)
    print("自适应多周期布林带交易工作台 - Phase 2 (多周期共振)")
    print("=" * 60)

    config = get_config()
    ensure_dirs()
    print(f"标的: {config.symbol_name}({config.symbol})")
    print(f"多周期共振: 启用")
    print(f"周期: {config.periods}")
    print(f"共振规则: {'全部周期确认' if config.resonance_require_all else '至少2周期确认'}")

    mp_result = run_multi_period_backtest(config.symbol, config.initial_capital)

    print("\n单周期策略详情:")
    print_performance_report(mp_result.single_result)

    print("\n多周期策略详情:")
    print_performance_report(mp_result.multi_result)

    save_multi_period_report(mp_result)


def main():
    """主入口：根据命令行参数选择 Phase"""
    parser = argparse.ArgumentParser(
        description="自适应多周期布林带交易工作台",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_backtest.py              # 默认运行 Phase 1 (单周期)
  python run_backtest.py --phase2    # 运行 Phase 2 (多周期共振)
        """
    )

    parser.add_argument(
        "--phase2",
        action="store_true",
        help="运行 Phase 2 (多周期共振回测)"
    )

    args = parser.parse_args()

    if args.phase2:
        main_phase2()
    else:
        main_phase1()

    print("\n" + "=" * 60)
    print("回测完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
