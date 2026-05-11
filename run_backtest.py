#!/usr/bin/env python
"""
自适应多周期布林带交易工作台 - MVP 主入口
一键运行完整回测
"""

from src.config import get_config, ensure_dirs
from src.data_fetcher import get_stock_data
from src.bollinger import calculate_bollinger
from src.signals import generate_signals
from src.backtest import run_backtest
from src.output import save_backtest_report


def main():
    """主函数：运行完整回测流程"""
    print("=" * 60)
    print("自适应多周期布林带交易工作台 - MVP")
    print("=" * 60)

    # 1. 初始化配置
    config = get_config()
    ensure_dirs()
    print(f"标的: {config.symbol_name}({config.symbol})")
    print(f"布林带参数: N={config.bollinger_n}, M={config.bollinger_m}")
    print(f"初始资金: ¥{config.initial_capital:,.2f}")

    # 2. 获取数据
    df = get_stock_data()

    # 3. 计算布林带
    df = calculate_bollinger(df)

    # 4. 生成信号
    df = generate_signals(df)

    # 5. 运行回测
    print("\n运行回测...")
    result = run_backtest(df)

    # 6. 输出结果
    save_backtest_report(result)

    # 7. 打印最后20天数据预览
    print("\n最后20天数据预览:")
    cols = ["date", "close", "ma_mid", "boll_up", "boll_down", "buy_signal", "sell_signal", "portfolio_value"]
    print(result.df.tail(20)[cols].to_string(index=False))

    print("\n" + "=" * 60)
    print("回测完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
