"""配置管理模块"""

import os
from dataclasses import dataclass
from typing import Optional


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
