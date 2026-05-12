#!/usr/bin/env python
"""快速验证 Phase 2 功能（使用样本数据）"""

import sys
sys.path.insert(0, '.')

from src.config import get_config
from src.data_fetcher import get_sample_data
from src.bollinger import calculate_bollinger
from src.indicators import calculate_all_indicators
from src.multi_period import calculate_all_for_period, align_multi_period_data, check_resonance_signals
from src.backtest import run_backtest


print("=" * 60)
print("Phase 2 快速验证")
print("=" * 60)

config = get_config()

# 1. 生成样本数据
print("\n1. 生成样本数据...")
daily = get_sample_data('000333', 120, 'daily')
h4 = get_sample_data('000333', 120, '4h')
print(f"   日线: {len(daily)} 条, 4小时: {len(h4)} 条")

# 2. 计算指标
print("\n2. 计算指标...")
daily_full = calculate_all_for_period(daily, config)
h4_full = calculate_all_for_period(h4, config)
print(f"   指标计算完成")

# 3. 对齐数据
print("\n3. 对齐多周期数据...")
aligned = align_multi_period_data(daily_full, h4_full, None)
print(f"   对齐完成: {len(aligned)} 条")

# 4. 检查共振信号
print("\n4. 检查共振信号...")
result = check_resonance_signals(aligned, config)
buy_count = (result['resonance_buy'] == 1).sum()
sell_count = (result['resonance_sell'] == 1).sum()
print(f"   共振买入信号: {buy_count} 个")
print(f"   共振卖出信号: {sell_count} 个")

# 5. 测试回测
print("\n5. 运行回测...")
test_df = result.copy()
test_df['buy_signal'] = test_df['resonance_buy']
test_df['sell_signal'] = test_df['resonance_sell']
bt_result = run_backtest(test_df, 100000)
print(f"   回测完成: 总收益率 {bt_result.total_return:.2%}")
print(f"   交易次数: {bt_result.total_trades}")

print("\n" + "=" * 60)
print("✅ Phase 2 核心功能验证通过!")
print("=" * 60)
print("\n运行完整 Phase 2 回测: python run_backtest.py --phase2")
print("运行 Phase 1 (基准) 回测: python run_backtest.py")
