# ⚠️ streamlit 和 fpdf 模块无法在本地 sandbox 中运行，仅供部署使用。
# 如果你想测试功能，请在本地 Python 环境中使用：
# pip install streamlit fpdf openpyxl plotly

try:
    import streamlit as st
    from types import SimpleNamespace
except ModuleNotFoundError:
    print("[警告] 当前环境无法使用 streamlit，请在本地或 Cloud 上运行。streamlit 功能已被禁用。")
    class DummySidebar:
        def markdown(self, *args, **kwargs): pass
        def multiselect(self, *args, **kwargs): return []
        def dataframe(self, *args, **kwargs): pass
        def write(self, *args, **kwargs): pass
        def plotly_chart(self, *args, **kwargs): pass
        def selectbox(self, *args, **kwargs): return '中文'

    class DummyStreamlit:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    st = DummyStreamlit()
    st.sidebar = DummySidebar()

try:
    from fpdf import FPDF
except ModuleNotFoundError:
    print("[警告] 当前环境无法使用 fpdf，PDF 功能将被禁用。")
    class FPDF:
        def add_page(self): pass
        def set_font(self, *a, **k): pass
        def cell(self, *a, **k): pass
        def image(self, *a, **k): pass
        def output(self, *a, **k): return b''

import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import xlsxwriter
from datetime import datetime
import os

LANG_OPTIONS = {
    '中文': {
        'title': "📈 自动化交易分析报告生成器",
        'upload_label': "请上传一个或多个 Rithmic / ATAS 导出的 CSV 文件：",
        'symbol_select': "选择要分析的品种（可多选）:",
        'load_success': "已加载 {count} 条成交记录",
        'pdf_download': "📄 下载账户 {acc} 报告",
        'metrics': "📌 核心统计",
        'sharpe': "**夏普比率：**",
        'winrate': "**胜率：**",
        'profit_ratio': "**盈亏比：**",
        'drawdown': "**最大回撤：**",
        'win_streak': "**最长连续盈利笔数：**",
        'loss_streak': "**最长连续亏损笔数：**",
        'snapshot_title': "📊 快照对比分析"
    },
    'English': {
        'title': "📈 Automated Trading Report Generator",
        'upload_label': "Upload one or more Rithmic / ATAS exported CSV files:",
        'symbol_select': "Select symbols to analyze:",
        'load_success': "Loaded {count} filled trades",
        'pdf_download': "📄 Download Report for {acc}",
        'metrics': "📌 Key Metrics",
        'sharpe': "**Sharpe Ratio:**",
        'winrate': "**Win Rate:**",
        'profit_ratio': "**Profit Factor:**",
        'drawdown': "**Max Drawdown:**",
        'win_streak': "**Longest Win Streak:**",
        'loss_streak': "**Longest Loss Streak:**",
        'snapshot_title': "📊 Snapshot Comparison"
    }
}

# ✅ 必须先设置页面配置，再做其他任何 Streamlit 操作
st.set_page_config(page_title="📈 自动化交易分析报告生成器", layout="wide")

# 再进行语言选择和界面设置
lang_choice = st.sidebar.selectbox("语言 / Language", options=list(LANG_OPTIONS.keys()), index=0)
lng = LANG_OPTIONS[lang_choice]

st.title(lng['title'])

SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

uploaded_files = st.file_uploader(lng['upload_label'], type="csv", accept_multiple_files=True)

if uploaded_files:
    @st.cache_data
    def load_and_clean_data(files):
        def extract_completed_orders(file):
            lines = file.getvalue().decode('utf-8').splitlines()
            start_index = None
            for i, line in enumerate(lines):
                if 'Completed Orders' in line:
                    start_index = i + 1
                    break
            if start_index is None:
                return pd.DataFrame()
            header = lines[start_index].replace('"', '').split(',')
            data = '\n'.join(lines[start_index + 1:])
            df = pd.read_csv(io.StringIO(data), names=header)
            return df

        dfs = [extract_completed_orders(f) for f in files]
        df_all = pd.concat(dfs, ignore_index=True)
        df_all = df_all[df_all['Status'] == 'Filled']
        df_all = df_all[[
            'Account', 'Buy/Sell', 'Symbol', 'Avg Fill Price', 'Qty To Fill',
            'Update Time (CST)', 'Commission Fill Rate', 'Closed Profit/Loss']]
        df_all.columns = ['账户', '方向', '品种', '价格', '数量', '时间', '手续费', '盈亏']
        df_all['时间'] = pd.to_datetime(df_all['时间'], errors='coerce')
        df_all['方向'] = df_all['方向'].map({'B': 'Buy', 'S': 'Sell'})
        df_all['价格'] = pd.to_numeric(df_all['价格'], errors='coerce')
        df_all['数量'] = pd.to_numeric(df_all['数量'], errors='coerce')
        df_all['手续费'] = pd.to_numeric(df_all['手续费'], errors='coerce').fillna(0)
        df_all['盈亏'] = pd.to_numeric(df_all['盈亏'], errors='coerce')
        df_all = df_all.dropna(subset=['时间', '价格', '方向'])
        df_all = df_all.sort_values('时间').reset_index(drop=True)
        return df_all

    df_trades = load_and_clean_data(uploaded_files)
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    df_trades.to_csv(os.path.join(SNAPSHOT_DIR, f'snapshot_{now_str}.csv'), index=False)
    st.success(lng['load_success'].format(count=len(df_trades)))

    all_symbols = sorted(df_trades['品种'].unique())
    selected_symbols = st.multiselect(lng['symbol_select'], all_symbols, default=all_symbols)
    df_trades = df_trades[df_trades['品种'].isin(selected_symbols)]

    df_trades['累计盈亏'] = df_trades['盈亏'].cumsum()
    df_trades['日期'] = df_trades['时间'].dt.date
    df_trades['小时'] = df_trades['时间'].dt.hour

    st.subheader("📈 Plotly 交互式图表")
    st.plotly_chart(px.line(df_trades, x='时间', y='累计盈亏', title='累计盈亏趋势'))
    st.plotly_chart(px.bar(df_trades.groupby('日期')['盈亏'].sum().reset_index(), x='日期', y='盈亏', title='每日盈亏'))
    st.plotly_chart(px.bar(df_trades.groupby('小时')['盈亏'].mean().reset_index(), x='小时', y='盈亏', title='每小时平均盈亏'))

    st.subheader(lng['metrics'])
    sharpe = df_trades['盈亏'].mean() / df_trades['盈亏'].std() * np.sqrt(252) if df_trades['盈亏'].std() != 0 else 0
    winrate = (df_trades['盈亏'] > 0).mean()
    profit_ratio = df_trades[df_trades['盈亏'] > 0]['盈亏'].mean() / -df_trades[df_trades['盈亏'] < 0]['盈亏'].mean() if not df_trades[df_trades['盈亏'] < 0].empty else np.nan
    max_drawdown = (df_trades['累计盈亏'] - df_trades['累计盈亏'].cummax()).min()
    results = df_trades['盈亏'].apply(lambda x: 1 if x > 0 else -1)
    streaks = results.ne(results.shift()).cumsum()
    max_win_streak = results[results > 0].groupby(streaks).size().max()
    max_loss_streak = results[results < 0].groupby(streaks).size().max()

    st.markdown(f"{lng['sharpe']} {sharpe:.2f}")
    st.markdown(f"{lng['winrate']} {winrate:.2%}")
    st.markdown(f"{lng['profit_ratio']} {profit_ratio:.2f}")
    st.markdown(f"{lng['drawdown']} {max_drawdown:.2f}")
    st.markdown(f"{lng['win_streak']} {max_win_streak}")
    st.markdown(f"{lng['loss_streak']} {max_loss_streak}")
