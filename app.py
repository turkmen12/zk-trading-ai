import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import io
from datetime import datetime

# 🎨 إعدادات الواجهة
st.set_page_config(page_title="ProTrader AI", layout="wide", page_icon="📈")
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button {font-size: 15px; font-weight: 600; padding: 10px 20px;}
    .metric-box {background: #0e1117; border: 1px solid #262730; border-radius: 8px; padding: 15px; text-align: center;}
    .strong-buy {color: #00ff00; font-weight: bold; font-size: 1.2rem;}
    .strong-sell {color: #ff4444; font-weight: bold; font-size: 1.2rem;}
    .neutral {color: #cccccc;}
    div[data-testid="stVerticalBlock"] > div {margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# 📦 قاعدة الأصول
ASSETS_DB = {
    "🥇 الذهب (Gold)": "GC=F", "🥈 الفضة (Silver)": "SI=F", "🛢️ النفط (Oil)": "CL=F",
    "📈 S&P 500": "^GSPC", "💻 Nasdaq": "^IXIC", "🇬🇧 FTSE 100": "^FTSE",
    "₿ Bitcoin": "BTC-USD", "Ξ Ethereum": "ETH-USD", "💶 EUR/USD": "EURUSD=X",
    "💷 GBP/USD": "GBPUSD=X", "🍎 Apple": "AAPL", "🚗 Tesla": "TSLA"
}

# 🔧 دوال مساعدة
def get_scalar(series):
    if hasattr(series, 'iloc'):
        val = series.iloc[-1]
        return float(val.item()) if hasattr(val, 'item') else float(val)
    return float(series)

def calc_atr(df, period=14):
    tr = pd.DataFrame(index=df.index)
    tr['h_l'] = df['High'] - df['Low']
    tr['h_pc'] = (df['High'] - df['Close'].shift(1)).abs()
    tr['l_pc'] = (df['Low'] - df['Close'].shift(1)).abs()
    tr['max'] = tr[['h_l', 'h_pc', 'l_pc']].max(axis=1)
    return tr['max'].rolling(window=period).mean().iloc[-1]

def calc_macd(df):
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def calc_bollinger(df, period=20, std_dev=2):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower

def get_ai_score(df):
    price = get_scalar(df['Close'])
    rsi = get_scalar(df['RSI']) if not pd.isna(df['RSI'].iloc[-1]) else 50
    sma50 = get_scalar(df['SMA_50']) if not pd.isna(df['SMA_50'].iloc[-1]) else 0
    macd, signal, _ = calc_macd(df)
    macd_val = get_scalar(macd)
    sig_val = get_scalar(signal)
    
    score = 50
    if rsi < 30: score += 15
    elif rsi > 70: score -= 15
    if sma50 > 0 and price > sma50: score += 10
    elif sma50 > 0 and price < sma50: score -= 10
    if macd_val > sig_val: score += 10
    else: score -= 10
    return score

# 🖥️ الشريط الجانبي
with st.sidebar:
    st.header("️ الإعدادات")
    search = st.text_input("🔍 بحث عن أصل", "")
    filtered = {k:v for k,v in ASSETS_DB.items() if not search or search.lower() in k.lower() or search.lower() in v.lower()}
    selected_name = st.selectbox("الأصل", list(filtered.keys()) if filtered else list(ASSETS_DB.keys()))
    symbol = filtered.get(selected_name, ASSETS_DB[selected_name])
    
    use_custom = st.checkbox("📝 رمز مخصص")
    if use_custom: symbol = st.text_input("الرمز", symbol).strip().upper()
    
    st.divider()
    period = st.selectbox("المدة", ["1mo", "3mo", "6mo", "1y"], index=2)
    interval = st.selectbox("الإطار", ["1d", "4h", "1h", "15m"], index=0)
    
    st.subheader("المؤشرات")
    show_gann = st.checkbox("📐 Gann", True)
    show_smc = st.checkbox("🏦 SMC/ICT", True)
    show_elliott = st.checkbox("🌊 Elliott", False)
    show_bb = st.checkbox("📊 Bollinger Bands", False)
    show_macd = st.checkbox("📉 MACD", False)

# 🚀 المنطق الرئيسي
if st.sidebar.button("▶️ تشغيل التحليل", type="primary"):
    with st.spinner("⏳ جاري المعالجة..."):
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            if df.empty: st.error("❌ بيانات فارغة. جرب رمزاً آخر أو مدة أطول."); st.stop()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            
            # حساب المؤشرات الأساسية
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + gain/loss))
            df['SMA_50'] = df['Close'].rolling(50).mean()
            macd_line, sig_line, hist = calc_macd(df)
            bb_mid, bb_up, bb_low = calc_bollinger(df)
            atr_val = calc_atr(df)
            score = get_ai_score(df)
            
            last_price = get_scalar(df['Close'])
            last_rsi = get_scalar(df['RSI']) if not pd.isna(df['RSI'].iloc[-1]) else 50
            
            # 📊 التبويبات
            tab1, tab2, tab3, tab4 = st.tabs(["📈 الشارت المتقدم", "📡 مصفوفة الإشارات", "🛡️ إدارة المخاطر", "💾 تصدير البيانات"])
            
            with tab1:
                st.metric(" السعر", f"${last_price:.2f}")
                st.metric("📊 RSI", f"{last_rsi:.1f}")
                st.metric("🤖 التقييم الذكي", f"{score}/100")
                
                rows, heights = 2, [0.7, 0.3]
                if show_macd: rows, heights = 3, [0.5, 0.2, 0.3]
                
                fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                                    row_heights=heights, subplot_titles=("السعر", "MACD" if show_macd else "RSI", "الحجم") if show_macd else ("السعر", "RSI"))
                
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="سعر"), row=1, col=1)
                if show_bb:
                    fig.add_trace(go.Scatter(x=df.index, y=bb_up, mode="lines", name="BB Upper", line=dict(color="gray", dash="dot")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=bb_low, mode="lines", name="BB Lower", line=dict(color="gray", dash="dot")), row=1, col=1)
                
                if show_gann:
                    rng = df['High'].max() - df['Low'].min()
                    gann = df['Low'].min() + np.arange(len(df)) * (rng/len(df))
                    fig.add_trace(go.Scatter(x=df.index, y=gann, mode="lines", name="Gann 1x1", line=dict(color="purple", dash="dash")), row=1, col=1)
                
                if show_smc:
                    for i in range(2, len(df)):
                        if float(df['Low'].iloc[i]) > float(df['High'].iloc[i-2]):
                            fig.add_shape(type="rect", xref="x", yref="y", x0=df.index[i-2], y0=float(df['High'].iloc[i-2]),
                                          x1=df.index[i], y1=float(df['Low'].iloc[i]), fillcolor="rgba(0,255,0,0.1)", line=dict(width=0), layer="below", row=1, col=1)
                
                if show_elliott:
                    peaks = df[(df['High']==df['High'].rolling(5,center=True).max()) & (df['High'].diff()>0)]
                    troughs = df[(df['Low']==df['Low'].rolling(5,center=True).min()) & (df['Low'].diff()<0)]
                    fig.add_trace(go.Scatter(x=peaks.index, y=peaks['High'], mode="markers", name="قمم", marker=dict(color="red", symbol="triangle-down")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=troughs.index, y=troughs['Low'], mode="markers", name="قيعان", marker=dict(color="blue", symbol="triangle-up")), row=1, col=1)
                
                rsi_row = 2 if not show_macd else 3
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode="lines", name="RSI", line=dict(color="cyan")), row=rsi_row, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="red", row=rsi_row, col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="green", row=rsi_row, col=1)
                
                if show_macd:
                    fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=hist.apply(lambda x: 'green' if x>0 else 'red')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=macd_line, mode="lines", name="MACD", line=dict(color="blue")), row=2, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=sig_line, mode="lines", name="Signal", line=dict(color="orange")), row=2, col=1)
                
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=df['Volume'].apply(lambda x: '#26a69a' if df['Close'].iloc[df.index.get_loc(x)]>=df['Open'].iloc[df.index.get_loc(x)] else '#ef5350')), row=rows, col=1)
                fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                st.subheader("📡 مصفوفة الإشارات عبر الأطر الزمنية")
                tf_data = []
                for tf in ["15m", "1h", "4h", "1d"]:
                    try:
                        d = yf.download(symbol, period="1mo", interval=tf, progress=False)
                        if d.empty: continue
                        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
                        sc = get_ai_score(d)
                        sig = "شراء" if sc>=60 else "بيع" if sc<=40 else "محايد"
                        tf_data.append({"الإطار": tf, "التقييم": f"{sc}/100", "الإشارة": sig})
                    except: pass
                if tf_data: st.dataframe(pd.DataFrame(tf_data), use_container_width=True)
                else: st.info("لا تتوفر بيانات كافية للأطر المتعددة حالياً.")
            
            with tab3:
                st.subheader("🛡️ حاسبة إدارة المخاطر (ATR-Based)")
                col1, col2, col3 = st.columns(3)
                cap = col1.number_input("رأس المال ($)", 10000.0, step=500.0)
                risk_pct = col2.slider("نسبة المخاطرة (%)", 1.0, 5.0, 2.0)
                entry = col3.number_input("سعر الدخول", float(last_price))
                
                if atr_val and not np.isnan(atr_val):
                    sl = entry - (2 * atr_val)
                    tp = entry + (3 * atr_val)
                    risk_amt = cap * (risk_pct/100)
                    shares = risk_amt / (entry - sl) if entry > sl else 0
                    
                    st.success(f"✅ وقف الخسارة: `{sl:.2f}` | جني الأرباح: `{tp:.2f}`")
                    st.info(f" حجم الصفقة المقترح: `{shares:.2f}` وحدة | المخاطرة: `${risk_amt:.2f}`")
                else:
                    st.warning("️ لا يمكن حساب ATR بدقة. جرب إطاراً زمنياً أطول.")
            
            with tab4:
                st.subheader(" تصدير البيانات والشارت")
                csv = df.to_csv().encode('utf-8')
                st.download_button("📥 تحميل البيانات (CSV)", csv, f"{symbol}_data.csv", "text/csv")
                
                html_str = fig.to_html(include_plotlyjs='cdn')
                st.download_button("🖼️ تحميل الشارت (HTML تفاعلي)", html_str, f"{symbol}_chart.html", "text/html")
                
        except Exception as e:
            st.error(f"❌ خطأ: {str(e)}")
else:
    st.info(" اضبط الإعدادات من القائمة الجانبية ثم اضغط ▶️ تشغيل التحليل")
