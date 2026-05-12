"""数据获取模块 - 支持 AKShare 及多源 fallback、本地缓存"""

import os
import time
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from .config import get_config, ensure_dirs


def clean_filename_name(name: str) -> str:
    """
    清理股票名称用于文件名，替换特殊字符为下划线

    Args:
        name: 原始股票名称，如"*ST平安"、"美的集团"

    Returns:
        清理后的名称，如"_ST平安"、"美的集团"
    """
    # 替换特殊字符为下划线：空格、*、(、)、[、]、-、.、/、\
    return re.sub(r'[^\w一-鿿]', '_', name)


def get_cache_path(symbol: str, period: str, start_date: str, name: Optional[str] = None) -> str:
    """
    获取缓存文件路径

    Args:
        symbol: 股票代码
        period: 周期
        start_date: 开始日期
        name: 股票名称（可选），如果提供则使用新格式

    Returns:
        缓存文件路径
    """
    config = get_config()
    if name:
        clean_name = clean_filename_name(name)
        filename = f"{clean_name}_{symbol}_{period}_{start_date}.csv"
    else:
        filename = f"{symbol}_{period}_{start_date}.csv"
    return os.path.join(config.cache_dir, filename)


def get_cache_metadata_path(symbol: str, period: str, start_date: str, name: Optional[str] = None) -> str:
    """
    获取缓存元数据文件路径

    Args:
        symbol: 股票代码
        period: 周期
        start_date: 开始日期
        name: 股票名称（可选），如果提供则使用新格式

    Returns:
        元数据文件路径
    """
    config = get_config()
    if name:
        clean_name = clean_filename_name(name)
        filename = f"{clean_name}_{symbol}_{period}_{start_date}.meta.json"
    else:
        filename = f"{symbol}_{period}_{start_date}.meta.json"
    return os.path.join(config.cache_dir, filename)


def migrate_data_cache():
    """
    迁移旧格式缓存文件到新格式（包含名称）

    只会在有 config.symbol_name 的情况下迁移默认标的，
    其他标的需要通过 get_stock_data 传入 name 时自动迁移。
    """
    config = get_config()
    cache_dir = config.cache_dir

    if not os.path.exists(cache_dir):
        return

    migrated_count = 0

    # 先尝试迁移默认标的
    if config.symbol_name:
        default_name = config.symbol_name
        default_symbol = config.symbol

        for filename in os.listdir(cache_dir):
            # 匹配旧格式：{symbol}_{period}_{start_date}.csv 或 .meta.json
            if filename.startswith(f"{default_symbol}_"):
                old_path = os.path.join(cache_dir, filename)

                if filename.endswith(".csv"):
                    # 解析旧文件名
                    parts = filename[:-4].split("_")
                    if len(parts) >= 3:
                        symbol_part = parts[0]
                        period_part = parts[1]
                        start_date_part = "_".join(parts[2:])  # 处理 start_date 可能包含下划线的情况（虽然不应该）

                        # 检查是否已经有新文件
                        new_path = get_cache_path(symbol_part, period_part, start_date_part, default_name)
                        if not os.path.exists(new_path):
                            try:
                                os.rename(old_path, new_path)
                                migrated_count += 1
                                print(f"已迁移: {filename} -> {os.path.basename(new_path)}")
                            except Exception as e:
                                print(f"迁移失败 {filename}: {e}")

                elif filename.endswith(".meta.json"):
                    # 解析旧文件名
                    base_name = filename[:-10]  # 去掉 .meta.json
                    parts = base_name.split("_")
                    if len(parts) >= 3:
                        symbol_part = parts[0]
                        period_part = parts[1]
                        start_date_part = "_".join(parts[2:])

                        new_path = get_cache_metadata_path(symbol_part, period_part, start_date_part, default_name)
                        if not os.path.exists(new_path):
                            try:
                                os.rename(old_path, new_path)
                                migrated_count += 1
                                print(f"已迁移: {filename} -> {os.path.basename(new_path)}")
                            except Exception as e:
                                print(f"迁移失败 {filename}: {e}")

    if migrated_count > 0:
        print(f"数据缓存迁移完成，共迁移 {migrated_count} 个文件")


def load_from_cache(symbol: str, period: str, start_date: str, name: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    从本地缓存加载数据

    优先尝试新格式（有 name），如果不存在且提供了 name，则尝试迁移旧文件；
    如果没有 name 或迁移失败，则尝试旧格式。
    """
    # 先尝试新格式
    if name:
        cache_path_new = get_cache_path(symbol, period, start_date, name)
        if os.path.exists(cache_path_new):
            try:
                df = pd.read_csv(cache_path_new)
                print(f"Loaded from cache: {cache_path_new} ({len(df)} rows)")
                return df
            except Exception as e:
                print(f"Cache load failed (new format): {e}")

        # 尝试自动迁移旧文件
        cache_path_old = get_cache_path(symbol, period, start_date)
        if os.path.exists(cache_path_old):
            try:
                os.rename(cache_path_old, cache_path_new)
                print(f"自动迁移缓存: {os.path.basename(cache_path_old)} -> {os.path.basename(cache_path_new)}")
                df = pd.read_csv(cache_path_new)
                print(f"Loaded from cache: {cache_path_new} ({len(df)} rows)")
                return df
            except Exception as e:
                print(f"迁移失败，尝试加载旧格式: {e}")

    # 尝试旧格式
    cache_path_old = get_cache_path(symbol, period, start_date)
    if os.path.exists(cache_path_old):
        try:
            df = pd.read_csv(cache_path_old)
            print(f"Loaded from cache: {cache_path_old} ({len(df)} rows)")
            return df
        except Exception as e:
            print(f"Cache load failed: {e}")
    return None


def save_to_cache(df: pd.DataFrame, symbol: str, period: str, start_date: str, name: Optional[str] = None):
    """保存数据到本地缓存"""
    ensure_dirs()
    # 如果有 name，保存新格式后删除旧格式
    if name:
        cache_path_new = get_cache_path(symbol, period, start_date, name)
        cache_path_old = get_cache_path(symbol, period, start_date)
        try:
            df.to_csv(cache_path_new, index=False)
            print(f"Data cached to: {cache_path_new}")
            # 删除旧文件（如果存在）
            if os.path.exists(cache_path_old):
                try:
                    os.remove(cache_path_old)
                    print(f"已删除旧缓存: {os.path.basename(cache_path_old)}")
                except Exception as e:
                    print(f"删除旧缓存失败: {e}")
        except Exception as e:
            print(f"Cache save failed (new format): {e}")
    else:
        # 没有 name，只能用旧格式
        cache_path = get_cache_path(symbol, period, start_date)
        try:
            df.to_csv(cache_path, index=False)
            print(f"Data cached to: {cache_path}")
        except Exception as e:
            print(f"Cache save failed: {e}")


def load_cache_metadata(symbol: str, period: str, start_date: str, name: Optional[str] = None) -> Optional[dict]:
    """
    加载缓存元数据

    优先尝试新格式（有 name），如果不存在且提供了 name，则尝试迁移旧文件；
    如果没有 name 或迁移失败，则尝试旧格式。
    """
    # 先尝试新格式
    if name:
        meta_path_new = get_cache_metadata_path(symbol, period, start_date, name)
        if os.path.exists(meta_path_new):
            try:
                import json
                with open(meta_path_new, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Metadata load failed (new format): {e}")

        # 尝试自动迁移旧文件
        meta_path_old = get_cache_metadata_path(symbol, period, start_date)
        if os.path.exists(meta_path_old):
            try:
                os.rename(meta_path_old, meta_path_new)
                print(f"自动迁移元数据: {os.path.basename(meta_path_old)} -> {os.path.basename(meta_path_new)}")
                import json
                with open(meta_path_new, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"迁移元数据失败，尝试加载旧格式: {e}")

    # 尝试旧格式
    meta_path_old = get_cache_metadata_path(symbol, period, start_date)
    if os.path.exists(meta_path_old):
        try:
            import json
            with open(meta_path_old, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Metadata load failed: {e}")
    return None


def save_cache_metadata(metadata: dict, symbol: str, period: str, start_date: str, name: Optional[str] = None):
    """保存缓存元数据"""
    ensure_dirs()
    # 如果有 name，保存新格式后删除旧格式
    if name:
        meta_path_new = get_cache_metadata_path(symbol, period, start_date, name)
        meta_path_old = get_cache_metadata_path(symbol, period, start_date)
        try:
            import json
            with open(meta_path_new, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
            print(f"Metadata saved to: {meta_path_new}")
            # 删除旧文件（如果存在）
            if os.path.exists(meta_path_old):
                try:
                    os.remove(meta_path_old)
                    print(f"已删除旧元数据: {os.path.basename(meta_path_old)}")
                except Exception as e:
                    print(f"删除旧元数据失败: {e}")
        except Exception as e:
            print(f"Metadata save failed (new format): {e}")
    else:
        # 没有 name，只能用旧格式
        meta_path = get_cache_metadata_path(symbol, period, start_date)
        try:
            import json
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
            print(f"Metadata saved to: {meta_path}")
        except Exception as e:
            print(f"Metadata save failed: {e}")


def merge_and_deduplicate(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """合并两个 DataFrame 并按日期去重（保留最新的）"""
    if old_df is None or len(old_df) == 0:
        return new_df.sort_values("date").reset_index(drop=True)
    if new_df is None or len(new_df) == 0:
        return old_df.sort_values("date").reset_index(drop=True)

    # 合并并去重
    combined = pd.concat([old_df, new_df], ignore_index=True)
    # 按日期排序，保留最后出现的（最新的）
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    return combined.reset_index(drop=True)


def get_sample_data(symbol: str = "000333", days: int = 120, period: str = "daily") -> pd.DataFrame:
    """生成样本数据（当所有在线源不可用时使用）"""
    print(f"Using local sample data for {symbol} ({period})")
    np.random.seed(42)
    base_price = 60.0

    # 根据周期确定时间间隔
    if period in ["1h", "60", "60m"]:
        hours = days * 6  # 每天6小时交易时间
        delta = timedelta(hours=1)
        start_dt = datetime(2025, 1, 1, 9, 30)  # 9:30 开盘
    elif period in ["4h", "240", "240m"]:
        hours = days * 2  # 每天2个4小时K线
        delta = timedelta(hours=4)
        start_dt = datetime(2025, 1, 1, 9, 30)
    else:
        # 日线
        delta = timedelta(days=1)
        start_dt = datetime(2025, 1, 1)
        hours = days

    # 生成时间序列
    dates = []
    current_dt = start_dt
    for _ in range(hours):
        dates.append(current_dt.strftime("%Y-%m-%d %H:%M:%S" if "h" in period or "m" in period else "%Y-%m-%d"))
        current_dt += delta
        # 简单处理：跳过非交易时间（周末等），样本数据不做复杂处理

    returns = np.random.normal(0.001, 0.02, hours)
    prices = base_price * np.cumprod(1 + returns)
    high = prices * (1 + np.random.uniform(0, 0.015, hours))
    low = prices * (1 - np.random.uniform(0, 0.015, hours))
    open_prices = np.concatenate([[base_price], prices[:-1]])
    volume = np.random.randint(1000000, 5000000, hours)

    df = pd.DataFrame({
        "date": dates,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume
    })
    return df


def get_data_akshare_v1(symbol: str, start_date: str, period: str = "daily") -> pd.DataFrame:
    """AKShare 数据源 v1: stock_zh_a_hist"""
    import akshare as ak
    print(f"[2/3] Trying AKShare stock_zh_a_hist ({period})...")

    # 转换 period 参数为 AKShare 格式
    ak_period = "daily"
    if period in ["1h", "60", "60m"]:
        ak_period = "60"
    elif period in ["4h", "240", "240m"]:
        ak_period = "240"

    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=ak_period,
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


def get_data_akshare_v2(symbol: str, start_date: str, period: str = "daily") -> pd.DataFrame:
    """AKShare 数据源 v2: 使用 stock_zh_a_hist_tx (腾讯数据源)"""
    import akshare as ak
    from datetime import datetime

    print(f"[1/3] Trying AKShare stock_zh_a_hist_tx ({period})...")

    # 腾讯数据源可能不支持小时级，降级到日线
    if period not in ["daily", "d", "day"]:
        print(f"  AKShare v2 doesn't support {period}, falling back to daily-only")
        raise Exception("AKShare v2 only supports daily")

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


def _is_non_ashare(symbol: str) -> bool:
    """判断是否非 A 股（如港股），A 股代码为 6 位数字"""
    return len(symbol) != 6 or not symbol.isdigit()


def get_data_baostock(symbol: str, start_date: str, period: str = "daily") -> pd.DataFrame:
    """BaoStock 数据源"""
    try:
        import baostock as bs
        print(f"Trying BaoStock for {symbol} ({period})...")

        # 转换 period 参数
        bs_freq = "d"  # 默认日线
        if period in ["1h", "60", "60m"]:
            bs_freq = "60"
        elif period in ["4h", "240", "240m"]:
            # BaoStock 没有4小时线，尝试用1小时后聚合，或者返回日线
            print(f"  BaoStock doesn't support 4h directly, will use 1h")
            bs_freq = "60"

        lg = bs.login()
        if lg.error_code != '0':
            raise Exception(f"BaoStock login failed")

        symbol_bs = f"sz.{symbol}" if symbol.startswith('0') else f"sh.{symbol}"
        rs = bs.query_history_k_data_plus(
            symbol_bs,
            "date,time,open,high,low,close,volume",
            start_date=start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
            frequency=bs_freq,
            adjustflag="2"
        )
        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
        bs.logout()

        if len(data_list) == 0:
            raise Exception("BaoStock no data")

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 处理日期列
        if "time" in df.columns and bs_freq != "d":
            df["date"] = df["time"]  # 小时级用 time 列
            df = df.drop("time", axis=1)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        print(f"BaoStock success! {len(df)} rows")
        return df
    except Exception as e:
        print(f"BaoStock failed: {e}")
        raise


def get_data_hk_akshare(symbol: str, start_date: str, period: str = "daily") -> pd.DataFrame:
    """AKShare 港股历史数据"""
    import akshare as ak
    print(f"Trying AKShare stock_hk_hist ({period})...")

    if period not in ["daily", "d", "day"]:
        raise Exception("stock_hk_hist only supports daily period")

    # 转换日期格式: 20250101 -> 2025-01-01
    end_date = datetime.now().strftime("%Y%m%d")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_hk_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            # 标准化列名
            df = df[["日期", "开盘", "最高", "最低", "收盘", "成交量"]].copy()
            df.columns = ["date", "open", "high", "low", "close", "volume"]
            df["date"] = df["date"].astype(str)
            print(f"stock_hk_hist success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"stock_hk_hist attempt {attempt + 1} failed: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("stock_hk_hist unavailable")


def get_data_hk_daily_akshare(symbol: str, start_date: str, period: str = "daily") -> pd.DataFrame:
    """AKShare 港股新浪数据源（fallback）"""
    import akshare as ak
    print(f"Trying AKShare stock_hk_daily ({period})...")

    if period not in ["daily", "d", "day"]:
        raise Exception("stock_hk_daily only supports daily period")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            df["date"] = df["date"].astype(str)
            # 过滤日期范围
            df = df[df["date"] >= start_date]
            if len(df) == 0:
                raise Exception("stock_hk_daily no data after start_date filter")
            print(f"stock_hk_daily success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"stock_hk_daily attempt {attempt + 1} failed: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("stock_hk_daily unavailable")


def get_stock_data(
    symbol: Optional[str] = None,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    name: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False
) -> pd.DataFrame:
    """
    获取股票数据（统一入口） - 支持增量更新

    Args:
        symbol: 股票代码，默认使用配置中的标的
        period: 周期，默认使用配置
        start_date: 开始日期，默认使用配置
        name: 股票名称（可选），用于生成可读的缓存文件名
        use_cache: 是否使用缓存，默认 True
        force_refresh: 是否强制全量刷新，默认 False

    Returns:
        标准化 DataFrame，包含列：date, open, high, low, close, volume
    """
    import json
    config = get_config()
    symbol = symbol or config.symbol
    period = period or config.period
    start_date = start_date or config.start_date
    # 如果没有传入 name，尝试从配置获取
    if name is None and symbol == config.symbol:
        name = config.symbol_name

    print(f"=== Fetching data for {symbol}" + (f" ({name})" if name else "") + " ===")

    # Helper to fetch full data from sources
    def _fetch_full(source_start_date: str) -> tuple[pd.DataFrame, str]:
        if _is_non_ashare(symbol):
            # 港股等非 A 股：使用港股专用数据源
            sources = [
                ("AKShare stock_hk_hist", lambda: get_data_hk_akshare(symbol, source_start_date, period)),
                ("AKShare stock_hk_daily", lambda: get_data_hk_daily_akshare(symbol, source_start_date, period)),
            ]
        else:
            # A 股：使用 A 股数据源
            sources = [
                ("AKShare stock_zh_a_hist_tx", lambda: get_data_akshare_v2(symbol, source_start_date, period)),
                ("AKShare stock_zh_a_hist", lambda: get_data_akshare_v1(symbol, source_start_date, period)),
                ("BaoStock", lambda: get_data_baostock(symbol, source_start_date, period)),
            ]

        for source_name, func in sources:
            try:
                df = func()
                return df, source_name
            except Exception:
                continue
        raise Exception("All data sources unavailable for " + symbol)

    # 0. Force refresh: bypass all cache logic
    if force_refresh:
        print("Force refresh enabled, bypassing cache")
        df, source = _fetch_full(start_date)
        # Save with metadata
        save_to_cache(df, symbol, period, start_date, name)
        latest_date = df["date"].max()
        meta = {
            "symbol": symbol, "period": period, "start_date": start_date,
            "latest_date": latest_date, "last_updated": datetime.now().isoformat(),
            "source": source, "row_count": len(df), "integrity": "ok"
        }
        save_cache_metadata(meta, symbol, period, start_date, name)
        return df

    # 1. Try to load cache + metadata
    if use_cache:
        cached_df = load_from_cache(symbol, period, start_date, name)
        cached_meta = load_cache_metadata(symbol, period, start_date, name)

        if cached_df is not None:
            if cached_meta is None:
                # Old cache without metadata - do full refresh to create metadata
                print("Old cache found (no metadata), doing full refresh to create metadata")
                df, source = _fetch_full(start_date)
                save_to_cache(df, symbol, period, start_date, name)
                latest_date = df["date"].max()
                meta = {
                    "symbol": symbol, "period": period, "start_date": start_date,
                    "latest_date": latest_date, "last_updated": datetime.now().isoformat(),
                    "source": source, "row_count": len(df), "integrity": "ok"
                }
                save_cache_metadata(meta, symbol, period, start_date, name)
                return df
            else:
                # Check if we need incremental update
                today = datetime.now().strftime("%Y-%m-%d")
                latest_date = cached_meta.get("latest_date", "")
                if latest_date < today:
                    print(f"Cache outdated (latest: {latest_date} < today: {today}), fetching incremental data")
                    # Calculate incremental start date: latest_date + 1 day
                    try:
                        from datetime import timedelta
                        dt = datetime.strptime(latest_date[:10], "%Y-%m-%d")
                        inc_start_date = (dt + timedelta(days=1)).strftime("%Y%m%d")
                    except Exception:
                        inc_start_date = start_date  # Fallback if date parsing fails
                    # Fetch incremental data
                    inc_df, source = _fetch_full(inc_start_date)
                    if len(inc_df) > 0:
                        # Merge and save
                        merged_df = merge_and_deduplicate(cached_df, inc_df)
                        save_to_cache(merged_df, symbol, period, start_date, name)
                        new_latest = merged_df["date"].max()
                        new_meta = cached_meta.copy()
                        new_meta.update({
                            "latest_date": new_latest, "last_updated": datetime.now().isoformat(),
                            "source": f"{cached_meta.get('source', '')} + {source}",
                            "row_count": len(merged_df)
                        })
                        save_cache_metadata(new_meta, symbol, period, start_date, name)
                        return merged_df
                    else:
                        # No new data, return cached
                        print("No new data available, returning cached data")
                        return cached_df
                else:
                    # Cache is fresh
                    print(f"Cache is fresh (latest: {latest_date})")
                    return cached_df

    # 2. No cache at all - full fetch
    df, source = _fetch_full(start_date)
    save_to_cache(df, symbol, period, start_date, name)
    latest_date = df["date"].max()
    meta = {
        "symbol": symbol, "period": period, "start_date": start_date,
        "latest_date": latest_date, "last_updated": datetime.now().isoformat(),
        "source": source, "row_count": len(df), "integrity": "ok"
    }
    save_cache_metadata(meta, symbol, period, start_date, name)
    return df


from typing import List, Dict, Tuple
from .watchlist import StockInfo


def fetch_batch_data(
    stocks: List[StockInfo],
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
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
        name = stock.name
        if show_progress:
            print(f"\n[{i}/{total}] Processing {symbol} - {name}")

        try:
            df = get_stock_data(
                symbol=symbol,
                period=period,
                start_date=start_date,
                name=name,
                use_cache=use_cache,
                force_refresh=force_refresh
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
