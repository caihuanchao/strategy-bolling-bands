"""数据获取模块 - 支持 AKShare 及多源 fallback、本地缓存"""

import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from .config import get_config, ensure_dirs


def get_cache_path(symbol: str, period: str, start_date: str) -> str:
    """获取缓存文件路径"""
    config = get_config()
    filename = f"{symbol}_{period}_{start_date}.csv"
    return os.path.join(config.cache_dir, filename)


def load_from_cache(symbol: str, period: str, start_date: str) -> Optional[pd.DataFrame]:
    """从本地缓存加载数据"""
    cache_path = get_cache_path(symbol, period, start_date)
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path)
            print(f"Loaded from cache: {cache_path} ({len(df)} rows)")
            return df
        except Exception as e:
            print(f"Cache load failed: {e}")
    return None


def save_to_cache(df: pd.DataFrame, symbol: str, period: str, start_date: str):
    """保存数据到本地缓存"""
    ensure_dirs()
    cache_path = get_cache_path(symbol, period, start_date)
    try:
        df.to_csv(cache_path, index=False)
        print(f"Data cached to: {cache_path}")
    except Exception as e:
        print(f"Cache save failed: {e}")


def get_sample_data(symbol: str = "000333", days: int = 120) -> pd.DataFrame:
    """生成样本数据（当所有在线源不可用时使用）"""
    print(f"Using local sample data for {symbol}")
    np.random.seed(42)
    base_price = 60.0
    dates = [(datetime(2025, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)
    high = prices * (1 + np.random.uniform(0, 0.015, days))
    low = prices * (1 - np.random.uniform(0, 0.015, days))
    open_prices = np.concatenate([[base_price], prices[:-1]])
    volume = np.random.randint(1000000, 5000000, days)

    df = pd.DataFrame({
        "date": dates,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume
    })
    return df


def get_data_akshare_v1(symbol: str, start_date: str) -> pd.DataFrame:
    """AKShare 数据源 v1: stock_zh_a_hist"""
    import akshare as ak
    print(f"[1/3] Trying AKShare stock_zh_a_hist...")
    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                adjust="qfq"
            )
            df = df[["日期", "开盘", "最高", "最低", "收盘", "成交量"]].copy()
            df.columns = ["date", "open", "high", "low", "close", "volume"]
            df["date"] = df["date"].astype(str)
            print(f"AKShare v1 success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"v1 attempt {attempt + 1} failed: {type(e).__name__}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("AKShare v1 unavailable")


def get_data_akshare_v2(symbol: str, start_date: str) -> pd.DataFrame:
    """AKShare 数据源 v2: 使用 stock_zh_a_hist_tx (腾讯数据源)"""
    import akshare as ak
    from datetime import datetime

    print(f"[2/3] Trying AKShare stock_zh_a_hist_tx...")
    # stock_zh_a_hist_tx 需要带市场前缀的股票代码
    symbol_tx = f"sz{symbol}" if symbol.startswith('0') or symbol.startswith('3') else f"sh{symbol}"

    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist_tx(
                symbol=symbol_tx,
                start_date=f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}",
                end_date=datetime.now().strftime("%Y-%m-%d"),
                adjust="qfq"
            )
            # 腾讯数据源返回的列名不同，需要转换
            df = df[["date", "open", "high", "low", "close", "amount"]].copy()
            df.columns = ["date", "open", "high", "low", "close", "volume"]
            df["date"] = df["date"].astype(str)
            print(f"AKShare v2 (tx) success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"v2 attempt {attempt + 1} failed: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("AKShare v2 unavailable")


def get_data_baostock(symbol: str, start_date: str) -> pd.DataFrame:
    """BaoStock 数据源"""
    try:
        import baostock as bs
        print(f"Trying BaoStock for {symbol}...")
        lg = bs.login()
        if lg.error_code != '0':
            raise Exception(f"BaoStock login failed")

        symbol_bs = f"sz.{symbol}" if symbol.startswith('0') else f"sh.{symbol}"
        rs = bs.query_history_k_data_plus(
            symbol_bs,
            "date,open,high,low,close,volume",
            start_date=start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
            frequency="d",
            adjustflag="2"
        )
        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
        bs.logout()

        if len(data_list) == 0:
            raise Exception("BaoStock no data")

        df = pd.DataFrame(data_list, columns=rs.fields)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        print(f"BaoStock success! {len(df)} rows")
        return df
    except Exception as e:
        print(f"BaoStock failed: {e}")
        raise


def get_stock_data(
    symbol: Optional[str] = None,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    获取股票数据（统一入口）

    Args:
        symbol: 股票代码，默认使用配置中的标的
        period: 周期，默认使用配置
        start_date: 开始日期，默认使用配置
        use_cache: 是否使用缓存，默认 True

    Returns:
        标准化 DataFrame，包含列：date, open, high, low, close, volume
    """
    config = get_config()
    symbol = symbol or config.symbol
    period = period or config.period
    start_date = start_date or config.start_date

    print(f"=== Fetching data for {symbol} ===")

    # 1. 尝试从缓存加载
    if use_cache:
        cached = load_from_cache(symbol, period, start_date)
        if cached is not None:
            return cached

    # 2. 尝试各数据源
    sources = [
        ("AKShare stock_zh_a_hist", lambda: get_data_akshare_v1(symbol, start_date)),
        ("AKShare stock_zh_a_hist_tx", lambda: get_data_akshare_v2(symbol, start_date)),
        ("BaoStock", lambda: get_data_baostock(symbol, start_date)),
    ]

    for name, func in sources:
        try:
            df = func()
            save_to_cache(df, symbol, period, start_date)
            return df
        except Exception:
            continue

    # 3. 所有源失败，使用样本数据
    print("All online sources unavailable, using local sample data")
    df = get_sample_data(symbol)
    save_to_cache(df, symbol, period, start_date)
    return df


from typing import List, Dict, Tuple
from .watchlist import StockInfo


def fetch_batch_data(
    stocks: List[StockInfo],
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    use_cache: bool = True,
    request_interval: float = 0.3,
    show_progress: bool = True
) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    批量获取多只股票数据

    Args:
        stocks: StockInfo 列表
        period: 周期
        start_date: 开始日期
        use_cache: 是否使用缓存
        request_interval: 请求间隔（秒），防限流
        show_progress: 是否显示进度

    Returns:
        (成功数据字典 {symbol: df}, 失败股票列表)
    """
    config = get_config()
    period = period or config.period
    start_date = start_date or config.start_date

    data_dict = {}
    failed_symbols = []
    total = len(stocks)

    for i, stock in enumerate(stocks, 1):
        symbol = stock.symbol
        if show_progress:
            print(f"\n[{i}/{total}] Processing {symbol} - {stock.name}")

        try:
            df = get_stock_data(
                symbol=symbol,
                period=period,
                start_date=start_date,
                use_cache=use_cache
            )
            data_dict[symbol] = df
        except Exception as e:
            print(f"⚠️  Failed to fetch {symbol}: {type(e).__name__}")
            failed_symbols.append(symbol)

        # 最后一只股票不需要等
        if i < total and request_interval > 0:
            time.sleep(request_interval)

    # 总结
    print(f"\n{'='*60}")
    print(f"Batch fetch complete: {len(data_dict)}/{total} succeeded")
    if failed_symbols:
        print(f"Failed ({len(failed_symbols)}): {', '.join(failed_symbols)}")
    print(f"{'='*60}")

    return data_dict, failed_symbols
