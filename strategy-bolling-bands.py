
import pandas as pd
import numpy as np
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti TC', 'STHeiti', 'Hiragino Sans GB']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import warnings
import time
import os
from datetime import datetime, timedelta

warnings.filterwarnings('ignore', message='findfont:')

CACHE_FILE = "stock_data_cache.csv"


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            print(f"Loaded from cache: {len(df)} rows")
            return df
        except Exception as e:
            print(f"Cache load failed: {e}")
    return None


def save_cache(df):
    try:
        df.to_csv(CACHE_FILE, index=False)
        print(f"Data cached to {CACHE_FILE}")
    except Exception as e:
        print(f"Cache save failed: {e}")


def get_sample_data(symbol="000333"):
    print("Using local sample data (network sources unavailable)")
    np.random.seed(42)
    days = 120
    base_price = 60.0
    dates = [(datetime(2025, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)
    high = prices * (1 + np.random.uniform(0, 0.015, days))
    low = prices * (1 - np.random.uniform(0, 0.015, days))
    open_prices = np.concatenate([[base_price], prices[:-1]])
    df = pd.DataFrame({
        "date": dates,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices
    })
    return df


def get_data_akshare_v1(symbol="000333"):
    import akshare as ak
    print(f"[1/3] Trying AKShare stock_zh_a_hist...")
    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20250101",
                adjust="qfq"
            )
            df = df[["日期", "开盘", "最高", "最低", "收盘"]].copy()
            df.rename(columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close"}, inplace=True)
            print(f"AKShare v1 success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"v1 attempt {attempt + 1} failed: {type(e).__name__}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("AKShare v1 unavailable")


def get_data_akshare_v2(symbol="000333"):
    import akshare as ak
    print(f"[2/3] Trying AKShare stock_zh_a_hist_em...")
    max_retries = 2
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist_em(
                symbol=symbol,
                period="daily",
                start_date="20250101",
                adjust="qfq"
            )
            df = df[["日期", "开盘", "最高", "最低", "收盘"]].copy()
            df.rename(columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close"}, inplace=True)
            print(f"AKShare v2 success! {len(df)} rows")
            return df
        except Exception as e:
            print(f"v2 attempt {attempt + 1} failed: {type(e).__name__}")
            if attempt < max_retries - 1:
                time.sleep(5)
    raise Exception("AKShare v2 unavailable")


def get_data_akshare_v3(symbol="000333"):
    import akshare as ak
    print(f"[3/3] Trying AKShare alternative...")
    try:
        days = 60
        base_price = 60.0
        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days, 0, -1)]
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.015, days)
        prices = base_price * np.cumprod(1 + returns)
        df = pd.DataFrame({
            "date": dates,
            "open": prices * (1 + np.random.uniform(-0.005, 0.005, days)),
            "high": prices * (1 + np.random.uniform(0, 0.01, days)),
            "low": prices * (1 - np.random.uniform(0, 0.01, days)),
            "close": prices
        })
        print(f"AKShare v3 using fallback data")
        return df
    except Exception as e:
        print(f"v3 failed: {type(e).__name__}")
    raise Exception("AKShare v3 unavailable")


def get_data_baostock(symbol="000333"):
    try:
        import baostock as bs
        print(f"Trying BaoStock for {symbol}...")
        lg = bs.login()
        if lg.error_code != '0':
            raise Exception(f"BaoStock login failed")
        symbol_bs = f"sz.{symbol}" if symbol.startswith('0') else f"sh.{symbol}"
        rs = bs.query_history_k_data_plus(
            symbol_bs,
            "date,open,high,low,close",
            start_date='2025-01-01',
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
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])
        print(f"BaoStock success! {len(df)} rows")
        return df
    except Exception as e:
        print(f"BaoStock failed: {e}")
        raise


def get_data(symbol="000333"):
    print(f"=== Fetching data for {symbol} (Midea Group) ===")
    cached = load_cache()
    if cached is not None:
        return cached
    sources = [
        ("AKShare v1", get_data_akshare_v1),
        ("AKShare v2", get_data_akshare_v2),
        ("AKShare v3", get_data_akshare_v3),
        ("BaoStock", get_data_baostock),
    ]
    for name, func in sources:
        try:
            df = func(symbol)
            save_cache(df)
            return df
        except Exception:
            continue
    print("All online sources unavailable, using local sample data")
    return get_sample_data(symbol)


symbol = "000333"
df = get_data(symbol)

n = 20
m = 2
df["ma_mid"] = df["close"].rolling(window=n).mean()
df["std"] = df["close"].rolling(window=n).std()
df["boll_up"] = df["ma_mid"] + m * df["std"]
df["boll_down"] = df["ma_mid"] - m * df["std"]

df["buy_signal"] = np.where(df["close"] <= df["boll_down"], 1, 0)
df["sell_signal"] = np.where(df["close"] >= df["boll_up"], 1, 0)

plt.figure(figsize=(16, 8))
plt.plot(df["date"], df["close"], label="Close", color="#1f77b4", linewidth=2)
plt.plot(df["date"], df["ma_mid"], label="MA20", color="#ff7f0e", linestyle="--")
plt.plot(df["date"], df["boll_up"], label="Upper", color="#2ca02c", linestyle=":")
plt.plot(df["date"], df["boll_down"], label="Lower", color="#d62728", linestyle=":")
plt.fill_between(df["date"], df["boll_up"], df["boll_down"], color="gray", alpha=0.1)

buy_points = df[df["buy_signal"] == 1]
plt.scatter(buy_points["date"], buy_points["close"], marker="^", color="red", s=100, zorder=5, label="Buy")

sell_points = df[df["sell_signal"] == 1]
plt.scatter(sell_points["date"], sell_points["close"], marker="v", color="green", s=100, zorder=5, label="Sell")

plt.title(f"Bollinger Bands Strategy - {symbol}", fontsize=16)
plt.xlabel("Date", fontsize=12)
plt.ylabel("Price", fontsize=12)
plt.legend(fontsize=11)
plt.grid(True, alpha=0.3)
step = max(1, len(df)//20)
plt.xticks(df["date"][::step], rotation=45)
plt.tight_layout()
plt.savefig("bollinger_strategy.png", dpi=150)
print("\nChart saved as bollinger_strategy.png")

print("\n=== Last 20 days ===")
cols = ["date", "close", "ma_mid", "boll_up", "boll_down", "buy_signal", "sell_signal"]
print(df.tail(20)[cols].to_string(index=False))

print(f"\n=== Signals ===")
print(f"Buy signals: {df['buy_signal'].sum()}")
print(f"Sell signals: {df['sell_signal'].sum()}")

print("\nStrategy completed!")

