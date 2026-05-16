"""配置管理模块"""

import os
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Config:
    """交易策略配置"""
    # 标的配置
    symbol: str = "000333"
    symbol_name: str = "美的集团"

    # 数据配置
    start_date: str = "20250101"
    period: str = "daily"
    cache_dir: str = "data"

    # 缓存配置
    cache_base_dir: str = "data/cache"
    cache_bollinger_dir: str = "data/cache/bollinger"

    # 布林带参数
    bollinger_n: int = 20
    bollinger_m: float = 2.0

    # 回测配置
    initial_capital: float = 100000.0
    commission_rate: float = 0.001  # 佣金率，双边
    stamp_duty_rate: float = 0.001  # 印花税率，卖出时单边
    position_size_type: str = "fixed_amount"  # fixed_amount 或 fixed_shares
    position_size_value: float = 10000.0  # 每次交易金额或股数

    # 输出配置
    log_dir: str = "logs"
    plot_figsize: tuple = (16, 8)

    # === Phase 2: 多周期共振配置 ===
    # 多周期开关（默认关闭，保持向后兼容）
    multi_period_enabled: bool = False

    # 多周期列表：按优先级从高到低（主周期在前）
    periods: List[str] = ("daily", "4h", "1h")

    # 共振规则：是否需要所有周期都确认（True=严格，False=至少2个）
    resonance_require_all: bool = False

    # === Phase 2: MACD 配置 ===
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # === Phase 2: RSI 配置 ===
    rsi_period: int = 14
    rsi_overbought: float = 70.0  # 超买阈值
    rsi_oversold: float = 30.0  # 超卖阈值

    # 成交量增强配置
    volume_threshold: float = 1.5  # 成交量放大阈值
    volume_window: int = 20

    # === 多策略配置 ===
    active_strategy: str = "bollinger"  # 当前活跃策略 ID

    # === 双均线策略配置 ===
    dualma_fast: int = 5     # 快线周期 (EMA)
    dualma_slow: int = 20    # 慢线周期 (EMA)

    # === 三重确认策略配置（固定参数） ===
    triple_confirm_volume_a_threshold: float = 1.0  # A 级量比基础阈值
    triple_confirm_volume_s_threshold: float = 1.5  # S 级量比阈值
    triple_confirm_adx_threshold: int = 20          # ADX 震荡市阈值
    triple_confirm_ma50_window: int = 50            # MA50 趋势过滤窗口
    triple_confirm_rsi_long_low: float = 30.0       # 做多 RSI 下限
    triple_confirm_rsi_long_high: float = 65.0      # 做多 RSI 上限
    triple_confirm_rsi_short_low: float = 45.0      # 做空 RSI 下限
    triple_confirm_rsi_short_high: float = 70.0     # 做空 RSI 上限
    triple_confirm_rsi_overbought_exit: float = 75.0  # 超买出场阈值
    triple_confirm_volume_shrink_days: int = 3      # 缩量止跌检测天数

    # === KDJ + 布林带 + ATR 策略配置（固定参数） ===
    # KDJ
    kdj_n: int = 9
    kdj_overbought_k: float = 80.0
    kdj_overbought_d: float = 70.0
    kdj_overbought_j: float = 100.0
    kdj_oversold_k: float = 20.0
    kdj_oversold_d: float = 30.0
    kdj_oversold_j: float = 0.0

    # ATR
    atr_period: int = 14
    atr_stop_multiplier: float = 1.5  # 震荡环境止损倍数
    atr_trend_stop_multiplier: float = 2.0  # 趋势环境止损倍数

    # 环境判定阈值
    bb_slope_threshold: float = 0.005  # 中轨斜率阈值（弧度），低于此值视为走平
    atr_expand_threshold: float = 1.2  # ATR 扩张阈值（与5日前比）
    squeeze_bandwidth_percentile: float = 0.10  # 带宽处于历史最低10%视为Squeeze
    squeeze_lookback: int = 120  # Squeeze 检测回溯周期（约6个月日线）

    # KDJ + BB + ATR 信号分级阈值
    kdj_bb_atr_volume_a_threshold: float = 1.0   # A 级量比基础阈值
    kdj_bb_atr_volume_s_threshold: float = 1.3   # S 级量比阈值
    kdj_divergence_lookback: int = 60  # KDJ 背离检测回溯周期


def get_config() -> Config:
    """获取配置实例"""
    return Config()


def ensure_dirs():
    """确保必要目录存在"""
    config = get_config()
    os.makedirs(config.cache_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)
    os.makedirs(config.cache_base_dir, exist_ok=True)
    os.makedirs(config.cache_bollinger_dir, exist_ok=True)
