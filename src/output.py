"""输出与日志模块 - 格式化输出回测结果、保存交易记录、绘制图表"""

import os
import pandas as pd
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti TC', 'STHeiti', 'Hiragino Sans GB']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore', message='findfont:')
from typing import Any

from .config import get_config, ensure_dirs
from .backtest import BacktestResult, Trade


def print_performance_report(result: BacktestResult):
    """打印绩效报告到控制台"""
    print("\n" + "=" * 60)
    print(f"回测绩效报告 - {get_config().symbol_name}({get_config().symbol})")
    print("=" * 60)
    print(f"初始资金:     ¥{result.initial_capital:,.2f}")
    print(f"最终资金:     ¥{result.final_capital:,.2f}")
    print(f"总收益率:     {result.total_return*100:+.2f}%")
    print(f"年化收益率:   {result.cagr*100:+.2f}%")
    print(f"最大回撤:     {result.max_drawdown*100:.2f}%")
    print("-" * 60)
    print(f"总交易次数:   {result.total_trades}")
    print(f"盈利交易:     {result.winning_trades}")
    print(f"亏损交易:     {result.losing_trades}")
    print(f"胜率:         {result.win_rate*100:.2f}%")
    print(f"盈亏比:       {result.reward_risk_ratio:.2f}")
    print("=" * 60 + "\n")


def save_trades_to_csv(trades: list[Trade], filename: str = "trades.csv"):
    """保存交易记录到 CSV"""
    ensure_dirs()
    config = get_config()
    filepath = os.path.join(config.log_dir, filename)

    data = []
    for t in trades:
        data.append({
            "date": t.date,
            "type": t.type,
            "price": t.price,
            "shares": t.shares,
            "amount": t.amount,
            "commission": t.commission,
            "stamp_duty": t.stamp_duty,
            "total_cost": t.total_cost
        })

    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"交易记录已保存至: {filepath}")


def plot_strategy_chart(result: BacktestResult, filename: str = "strategy_chart.png"):
    """绘制策略图表：价格+布林带+信号点"""
    ensure_dirs()
    config = get_config()
    df = result.df
    filepath = os.path.join(config.log_dir, filename)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=config.plot_figsize, sharex=True, gridspec_kw={'height_ratios': [3, 1]})

    # 子图1：价格、布林带、信号点
    ax1.plot(df["date"], df["close"], label="Close", color="#1f77b4", linewidth=2)
    ax1.plot(df["date"], df["ma_mid"], label="MA20", color="#ff7f0e", linestyle="--")
    ax1.plot(df["date"], df["boll_up"], label="Upper", color="#2ca02c", linestyle=":")
    ax1.plot(df["date"], df["boll_down"], label="Lower", color="#d62728", linestyle=":")
    ax1.fill_between(df["date"], df["boll_up"], df["boll_down"], color="gray", alpha=0.1)

    buy_points = df[df["buy_signal"] == 1]
    ax1.scatter(buy_points["date"], buy_points["close"], marker="^", color="red", s=100, zorder=5, label="Buy")

    sell_points = df[df["sell_signal"] == 1]
    ax1.scatter(sell_points["date"], sell_points["close"], marker="v", color="green", s=100, zorder=5, label="Sell")

    ax1.set_title(f"Bollinger Bands Strategy - {config.symbol_name}({config.symbol})", fontsize=14)
    ax1.set_ylabel("Price", fontsize=12)
    ax1.legend(fontsize=10, loc="upper left")
    ax1.grid(True, alpha=0.3)

    # 子图2：净值曲线
    ax2.plot(df["date"], df["portfolio_value"], label="Portfolio Value", color="#9400d3", linewidth=2)
    ax2.axhline(y=result.initial_capital, color="gray", linestyle="--", alpha=0.5)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.set_ylabel("Portfolio Value", fontsize=12)
    ax2.legend(fontsize=10, loc="upper left")
    ax2.grid(True, alpha=0.3)

    # 调整日期标签
    step = max(1, len(df) // 20)
    ax1.set_xticks(df["date"][::step])
    ax1.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    print(f"策略图表已保存至: {filepath}")
    plt.close()


def save_backtest_report(result: BacktestResult):
    """保存完整回测报告（调用所有输出函数）"""
    print_performance_report(result)
    save_trades_to_csv(result.trades)
    plot_strategy_chart(result)


# ============================================
# 以下是新增：HTML 仪表板相关
# ============================================

from typing import List, Dict, Tuple
from .signals import Signal


def generate_dashboard_html(
    signals: List[Signal],
    data_dict: Dict[str, Tuple[str, pd.DataFrame]],
    output_path: str = "logs/dashboard.html",
    volume_threshold: float = 1.5
) -> str:
    """
    生成 HTML 仪表板

    Args:
        signals: 今日信号列表
        data_dict: 完整数据字典 {symbol: (name, df)}
        output_path: 输出路径
        volume_threshold: 成交量阈值（用于显示）

    Returns:
        生成的 HTML 文件路径
    """
    ensure_dirs()
    config = get_config()

    # 分开买入和卖出
    buy_signals = [s for s in signals if s.signal_type == "BUY"]
    sell_signals = [s for s in signals if s.signal_type == "SELL"]

    # 生成 HTML 内容
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>布林带策略工作台 - 今日信号</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f5f7fa; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        header p {{ font-size: 16px; opacity: 0.9; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
        .stat-value {{ font-size: 32px; font-weight: bold; }}
        .stat-value.buy {{ color: #e74c3c; }}
        .stat-value.sell {{ color: #27ae60; }}
        .stat-value.enhanced {{ color: #9b59b6; }}
        .stat-label {{ color: #7f8c8d; margin-top: 5px; }}
        h2 {{ margin: 30px 0 15px; color: #2c3e50; }}
        .table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; }}
        .table th {{ background: #34495e; color: white; padding: 15px; text-align: left; font-weight: 600; }}
        .table td {{ padding: 12px 15px; border-bottom: 1px solid #ecf0f1; }}
        .table tr:hover {{ background: #f8f9fa; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
        .badge-buy {{ background: #fee2e2; color: #dc2626; }}
        .badge-sell {{ background: #dcfce7; color: #16a34a; }}
        .badge-enhanced {{ background: #f3e8ff; color: #7c3aed; }}
        .badge-normal {{ background: #f1f5f9; color: #64748b; }}
        .tabs {{ display: flex; gap: 10px; margin-bottom: 20px; }}
        .tab {{ padding: 12px 24px; background: white; border-radius: 8px; cursor: pointer; border: none; font-size: 15px; font-weight: 500; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .tab.active {{ background: #667eea; color: white; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        footer {{ text-align: center; margin-top: 50px; padding: 20px; color: #7f8c8d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 布林带策略工作台</h1>
            <p>自选股: {len(data_dict)} 只 | 扫描时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>

        <!-- 统计卡片 -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value buy">{len(buy_signals)}</div>
                <div class="stat-label">买入信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value sell">{len(sell_signals)}</div>
                <div class="stat-label">卖出信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value enhanced">{len([s for s in signals if s.is_enhanced])}</div>
                <div class="stat-label">增强信号 (> {volume_threshold}x 量)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(data_dict)}</div>
                <div class="stat-label">扫描总数</div>
            </div>
        </div>

        <!-- Tab 切换 -->
        <div class="tabs">
            <button class="tab active" onclick="showTab('signals')">今日信号</button>
            <button class="tab" onclick="showTab('all')">全部概览</button>
        </div>

        <!-- Tab 1: 今日信号 -->
        <div id="tab-signals" class="tab-content active">
            <h2>📈 买入信号 ({len(buy_signals)})</h2>
            {_generate_signal_table(buy_signals)}

            <h2>📉 卖出信号 ({len(sell_signals)})</h2>
            {_generate_signal_table(sell_signals)}
        </div>

        <!-- Tab 2: 全部概览 -->
        <div id="tab-all" class="tab-content">
            <h2>📋 全部股票状态</h2>
            {_generate_overview_table(data_dict)}
        </div>

        <footer>
            <p>💡 提示：增强信号 = 有信号 + 成交量放大 > {volume_threshold}倍前20日均量</p>
        </footer>
    </div>

    <script>
        function showTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            event.target.classList.add('active');
        }}
    </script>
</body>
</html>
"""

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ 仪表板已生成: {output_path}")
    return output_path


def _generate_signal_table(signals: List[Signal]) -> str:
    """生成信号表格 HTML"""
    if not signals:
        return '<p style="padding:20px;color:#7f8c8d;">暂无信号</p>'

    rows = []
    for s in signals:
        enhanced_badge = '<span class="badge badge-enhanced">🟢 增强</span>' if s.is_enhanced else '<span class="badge badge-normal">⚪ 普通</span>'
        type_badge = f'<span class="badge badge-{s.signal_type.lower()}">{s.signal_type}</span>'
        volume_str = f"{s.volume_ratio:.1f}x" if s.volume_ratio else "-"

        rows.append(f"""
            <tr>
                <td><strong>{s.symbol}</strong></td>
                <td>{s.name}</td>
                <td>{type_badge} {enhanced_badge}</td>
                <td>¥{s.price:.2f}</td>
                <td>{volume_str}</td>
                <td>{s.date}</td>
            </tr>
        """)

    return f"""
        <table class="table">
            <thead>
                <tr><th>代码</th><th>名称</th><th>类型</th><th>价格</th><th>量比</th><th>日期</th></tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    """


def _generate_overview_table(data_dict: Dict[str, Tuple[str, pd.DataFrame]]) -> str:
    """生成全部股票概览表格 HTML"""
    rows = []

    for symbol, (name, df) in data_dict.items():
        if len(df) == 0:
            continue

        latest = df.iloc[-1]
        close = latest.get("close", 0)
        boll_up = latest.get("boll_up", 0)
        boll_mid = latest.get("ma_mid", 0)
        boll_down = latest.get("boll_down", 0)

        # 判断位置
        if pd.notna(close) and pd.notna(boll_up) and pd.notna(boll_down) and pd.notna(boll_mid):
            if boll_up > boll_down:  # 正常布林带
                if close >= boll_up:
                    position = "📌 上轨附近"
                    color = "#27ae60"
                elif close <= boll_down:
                    position = "📌 下轨附近"
                    color = "#e74c3c"
                elif close >= boll_mid:
                    position = "📌 中上区间"
                    color = "#3498db"
                else:
                    position = "📌 中下区间"
                    color = "#95a5a6"
            else:
                position = "-"
                color = "#ccc"
        else:
            position = "-"
            color = "#ccc"

        rows.append(f"""
            <tr>
                <td><strong>{symbol}</strong></td>
                <td>{name}</td>
                <td>¥{close:.2f}</td>
                <td>¥{boll_mid:.2f}</td>
                <td>¥{boll_up:.2f}</td>
                <td>¥{boll_down:.2f}</td>
                <td style="color:{color}">{position}</td>
            </tr>
        """)

    return f"""
        <table class="table">
            <thead>
                <tr><th>代码</th><th>名称</th><th>现价</th><th>中轨</th><th>上轨</th><th>下轨</th><th>位置</th></tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    """


def generate_dashboard_js(
    output_path: str = "logs/dashboard.html"
) -> str:
    """
    生成 JavaScript 驱动的 HTML 仪表盘，从缓存 CSV/JSON 加载数据

    Args:
        output_path: 输出文件路径

    Returns:
        生成的文件路径
    """
    ensure_dirs()

    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>布林带策略工作台 - 今日信号</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f5f7fa; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
        header h1 { font-size: 28px; margin-bottom: 10px; }
        header p { font-size: 16px; opacity: 0.9; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .stat-value { font-size: 32px; font-weight: bold; }
        .stat-value.buy { color: #e74c3c; }
        .stat-value.sell { color: #27ae60; }
        .stat-value.enhanced { color: #9b59b6; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        h2 { margin: 30px 0 15px; color: #2c3e50; }
        .table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; }
        .table th { background: #34495e; color: white; padding: 15px; text-align: left; font-weight: 600; }
        .table td { padding: 12px 15px; border-bottom: 1px solid #ecf0f1; }
        .table tr:hover { background: #f8f9fa; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .badge-buy { background: #fee2e2; color: #dc2626; }
        .badge-sell { background: #dcfce7; color: #16a34a; }
        .badge-enhanced { background: #f3e8ff; color: #7c3aed; }
        .badge-normal { background: #f1f5f9; color: #64748b; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab { padding: 12px 24px; background: white; border-radius: 8px; cursor: pointer; border: none; font-size: 15px; font-weight: 500; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .tab.active { background: #667eea; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .loading { text-align: center; padding: 40px; color: #7f8c8d; font-size: 18px; }
        .error { background: #fee; color: #c33; padding: 20px; border-radius: 10px; margin: 20px 0; }
        footer { text-align: center; margin-top: 50px; padding: 20px; color: #7f8c8d; font-size: 14px; }
        .scan-time { color: rgba(255,255,255,0.9); font-size: 14px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 布林带策略工作台</h1>
            <p id="subtitle">正在加载数据...</p>
            <p id="scan-time" class="scan-time"></p>
        </header>

        <!-- 统计卡片 -->
        <div id="stats-container" class="stats">
            <div class="stat-card">
                <div class="stat-value buy">-</div>
                <div class="stat-label">买入信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value sell">-</div>
                <div class="stat-label">卖出信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value enhanced">-</div>
                <div class="stat-label">增强信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">-</div>
                <div class="stat-label">扫描总数</div>
            </div>
        </div>

        <!-- Tab 切换 -->
        <div class="tabs">
            <button class="tab active" onclick="showTab('signals')">今日信号</button>
            <button class="tab" onclick="showTab('all')">全部概览</button>
        </div>

        <!-- Tab 1: 今日信号 -->
        <div id="tab-signals" class="tab-content active">
            <h2>📈 买入信号</h2>
            <div id="buy-signals-container" class="loading">加载中...</div>

            <h2>📉 卖出信号</h2>
            <div id="sell-signals-container" class="loading">加载中...</div>
        </div>

        <!-- Tab 2: 全部概览 -->
        <div id="tab-all" class="tab-content">
            <h2>📋 全部股票状态</h2>
            <div id="all-stocks-container" class="loading">全部概览功能需要加载每只股票的布林带数据，暂未实现</div>
        </div>

        <footer>
            <p id="footer-note">💡 提示: 增强信号 = 有信号 + 成交量放大 > 1.5倍前20日均量</p>
        </footer>
    </div>

    <script>
        // 全局数据
        let metadata = null;
        let signalsData = [];

        // Tab 切换
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            event.target.classList.add('active');
        }

        // 解析 CSV 字符串为对象数组
        function parseCSV(csvText) {
            const lines = csvText.trim().split('\\n');
            if (lines.length < 2) return [];

            const headers = lines[0].split(',');
            const result = [];

            for (let i = 1; i < lines.length; i++) {
                const values = lines[i].split(',');
                const obj = {};
                for (let j = 0; j < headers.length; j++) {
                    obj[headers[j].trim()] = values[j] ? values[j].trim() : '';
                }
                result.push(obj);
            }
            return result;
        }

        // 格式化时间显示
        function formatScanTime(isoString) {
            const date = new Date(isoString);
            return '扫描时间: ' + date.toLocaleString('zh-CN');
        }

        // 渲染统计卡片
        function renderStats() {
            if (!metadata) return;

            const statsContainer = document.getElementById('stats-container');
            statsContainer.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value buy">${metadata.buy_signals}</div>
                    <div class="stat-label">买入信号</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value sell">${metadata.sell_signals}</div>
                    <div class="stat-label">卖出信号</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value enhanced">${metadata.enhanced_signals}</div>
                    <div class="stat-label">增强信号 (> ${metadata.volume_threshold}x 量)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${metadata.total_stocks}</div>
                    <div class="stat-label">扫描总数</div>
                </div>
            `;

            // 更新页脚提示
            document.getElementById('footer-note').textContent =
                `💡 提示: 增强信号 = 有信号 + 成交量放大 > ${metadata.volume_threshold}倍前${metadata.volume_window}日均量`;
        }

        // 渲染信号表格
        function renderSignalTable(signals) {
            if (!signals || signals.length === 0) {
                return '<p style="padding:20px;color:#7f8c8d;">暂无信号</p>';
            }

            let rows = '';
            for (const s of signals) {
                const enhancedBadge = s.is_enhanced === 'TRUE' || s.is_enhanced === 'true'
                    ? '<span class="badge badge-enhanced">🟢 增强</span>'
                    : '<span class="badge badge-normal">⚪ 普通</span>';
                const typeBadge = `<span class="badge badge-${s.signal_type.toLowerCase()}">${s.signal_type}</span>`;
                const volumeStr = s.volume_ratio ? `${parseFloat(s.volume_ratio).toFixed(1)}x` : '-';

                rows += `
                    <tr>
                        <td><strong>${s.symbol}</strong></td>
                        <td>${s.name}</td>
                        <td>${typeBadge} ${enhancedBadge}</td>
                        <td>¥${parseFloat(s.price).toFixed(2)}</td>
                        <td>${volumeStr}</td>
                        <td>${s.date}</td>
                    </tr>
                `;
            }

            return `
                <table class="table">
                    <thead>
                        <tr><th>代码</th><th>名称</th><th>类型</th><th>价格</th><th>量比</th><th>日期</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        }

        // 渲染所有信号
        function renderSignals() {
            const buySignals = signalsData.filter(s => s.signal_type === 'BUY');
            const sellSignals = signalsData.filter(s => s.signal_type === 'SELL');

            document.getElementById('buy-signals-container').innerHTML = renderSignalTable(buySignals);
            document.getElementById('sell-signals-container').innerHTML = renderSignalTable(sellSignals);
        }

        // 主渲染函数
        function renderDashboard() {
            // 更新标题
            const subtitle = document.getElementById('subtitle');
            if (metadata) {
                subtitle.textContent = `自选股: ${metadata.total_stocks} 只`;
                document.getElementById('scan-time').textContent = formatScanTime(metadata.scan_time);
            } else {
                subtitle.textContent = '数据加载完成';
            }

            renderStats();
            renderSignals();
        }

        // 加载 JSON 数据
        async function loadJSON(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (e) {
                console.error('加载 JSON 失败:', e);
                return null;
            }
        }

        // 加载 CSV 数据
        async function loadCSV(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const text = await response.text();
                return parseCSV(text);
            } catch (e) {
                console.error('加载 CSV 失败:', e);
                return null;
            }
        }

        // 初始化加载
        async function init() {
            try {
                // 注意：路径相对于 HTML 文件位置（logs/ 下）
                metadata = await loadJSON('../data/cache/metadata.json');
                signalsData = await loadCSV('../data/cache/signals.csv');

                if (metadata === null || signalsData === null) {
                    throw new Error('无法加载缓存数据，请确认已运行过 python run_workbench.py');
                }

                renderDashboard();
            } catch (e) {
                // 显示错误信息
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '❌ 加载失败: ' + e.message +
                    '\\n\\n提示: 如果直接双击打开 HTML，浏览器可能因为安全策略阻止本地文件访问。' +
                    '请尝试使用本地服务器，例如运行: python -m http.server 8000，然后访问 http://localhost:8000/logs/dashboard.html';

                document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.stats'));
                document.getElementById('subtitle').textContent = '数据加载失败';
            }
        }

        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ JS 驱动仪表板已生成: {output_path}")
    return output_path


# === Phase 2: 多周期回测输出 ===
def print_multi_period_comparison(mp_result: Any):
    """打印多周期 vs 单周期对比报告"""
    single = mp_result.single_result
    multi = mp_result.multi_result

    print("\n" + "=" * 70)
    print("多周期共振策略 vs 单周期策略 - 对比报告")
    print("=" * 70)

    # 表格形式对比
    print(f"\n{'指标':<20} {'单周期(基准)':<15} {'多周期共振':<15} {'差异':<15}")
    print("-" * 70)

    # 收益率
    diff_return = multi.total_return - single.total_return
    print(f"{'总收益率':<20} {single.total_return*100:>+12.2f}% {multi.total_return*100:>+12.2f}% {diff_return*100:>+12.2f}%")

    # 年化
    diff_cagr = multi.cagr - single.cagr
    print(f"{'年化收益率':<20} {single.cagr*100:>+12.2f}% {multi.cagr*100:>+12.2f}% {diff_cagr*100:>+12.2f}%")

    # 最大回撤
    diff_dd = single.max_drawdown - multi.max_drawdown  # 负的更少是变好
    print(f"{'最大回撤':<20} {single.max_drawdown*100:>12.2f}% {multi.max_drawdown*100:>12.2f}% {diff_dd*100:>12.2f}%")

    # 胜率
    diff_win = multi.win_rate - single.win_rate
    print(f"{'胜率':<20} {single.win_rate*100:>12.2f}% {multi.win_rate*100:>12.2f}% {diff_win*100:>12.2f}%")

    # 盈亏比
    diff_rr = multi.reward_risk_ratio - single.reward_risk_ratio
    print(f"{'盈亏比':<20} {single.reward_risk_ratio:>12.2f} {multi.reward_risk_ratio:>12.2f} {diff_rr:>12.2f}")

    # 交易次数
    diff_trades = multi.total_trades - single.total_trades
    print(f"{'交易次数':<20} {single.total_trades:>12} {multi.total_trades:>12} {diff_trades:>12}")

    print("-" * 70)

    # 总结
    print("\n" + "-" * 70)
    print("总结:")
    if diff_return > 0:
        print(f"  ✅ 多周期策略胜出: 收益率提升 {diff_return*100:.2f}%")
    else:
        print(f"  ⚠️  单周期策略表现更好: 差异 {diff_return*100:.2f}%")

    if diff_dd > 0:
        print(f"  ✅ 回撤优化: 最大回撤减少 {diff_dd*100:.2f}%")
    else:
        print(f"  ⚠️  回撤变大: {abs(diff_dd)*100:.2f}%")
    print("-" * 70 + "\n")


def plot_multi_period_comparison(mp_result: Any, filename: str = "comparison_chart.png"):
    """绘制多周期 vs 单周期净值对比图"""
    from .config import get_config, ensure_dirs
    ensure_dirs()
    config = get_config()
    filepath = f"{config.log_dir}/{filename}"

    single = mp_result.single_result
    multi = mp_result.multi_result

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))

    # 归一化净值曲线（都从 1 开始）
    single_norm = pd.Series(single.portfolio_values) / single.initial_capital
    multi_norm = pd.Series(multi.portfolio_values) / multi.initial_capital
    x_dates = single.df["date"] if len(single.df) == len(single_norm) else range(len(single_norm))

    ax.plot(x_dates, single_norm, label="单周期(基准)", color="#1f77b4", linewidth=2)
    ax.plot(x_dates, multi_norm, label="多周期共振", color="#ff7f0e", linewidth=2)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5)

    ax.set_title("策略对比 - 净值曲线 (归一化)", fontsize=14)
    ax.set_ylabel("净值倍数", fontsize=12)
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(True, alpha=0.3)

    # 日期标签
    if hasattr(x_dates, '__len__') and len(x_dates) > 0:
        step = max(1, len(x_dates) // 20)
        if hasattr(x_dates, 'iloc'):
            ax.set_xticks(x_dates[::step])
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    print(f"对比图表已保存至: {filepath}")
    plt.close()


def save_multi_period_report(mp_result: Any):
    """保存完整多周期回测报告"""
    print_multi_period_comparison(mp_result)
    save_trades_to_csv(mp_result.single_result.trades, "trades_single.csv")
    save_trades_to_csv(mp_result.multi_result.trades, "trades_multi.csv")
    plot_strategy_chart(mp_result.multi_result, "strategy_multi.png")
    plot_multi_period_comparison(mp_result)

