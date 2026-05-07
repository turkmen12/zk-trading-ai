import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 🎨 إعدادات الواجهة
st.set_page_config(page_title="ProTrader AI", layout="wide", page_icon="")
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button {font-size: 14px; font-weight: 600; padding: 8px 16px;}
    .signal-box {background: #0e1117; border-left: 4px solid #00ff00; padding: 15px; border-radius: 8px; margin: 10px 0;}
    .signal-sell {border-left-color: #ff4444;}
    .tp-stage {display: inline-block; background: #1a1d24; padding: 5px 10px; margin: 3px; border-radius: 5px; font-weight: bold;}
    .metric-card {background: #1a1d24; border-radius: 10px; padding: 15px; text-align: center;}
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

def calc_indicators(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain/loss))
    df['SMA_50'] = df['Close'].rolling(50).mean()
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df

def get_ai_signal(df):
    price = get_scalar(df['Close'])
    rsi = get_scalar(df['RSI']) if not pd.isna(df['RSI'].iloc[-1]) else 50
    sma50 = get_scalar(df['SMA_50']) if not pd.isna(df['SMA_50'].iloc[-1]) else 0
    macd = get_scalar(df['MACD'])
    sig = get_scalar(df['MACD_Signal'])
    
    score = 50
    if rsi < 30: score += 15
    elif rsi > 70: score -= 15
    if sma50 > 0 and price > sma50: score += 10
    elif sma50 > 0 and price < sma50: score -= 10
    if macd > sig: score += 10
    else: score -= 10
    
    direction = "شراء 🟢" if score >= 60 else "بيع 🔴" if score <= 40 else "انتظار ⚪"
    mult = 1 if "شراء" in direction else -1
    
    # ✅ وقف الخسارة: لا يتجاوز 200 نقطة
    sl = price - (200 * mult)
    
    # ✅ جني الأرباح: 3 مراحل بمجموع 500 نقطة (150 + 150 + 200)
    tp1 = price + (150 * mult)
    tp2 = price + (300 * mult)
    tp3 = price + (500 * mult)
    
    return direction, score, price, sl, tp1, tp2, tp3

# 🧠 إدارة الحالة للتفاعل الفوري
if 'df' not in st.session_state: st.session_state.df = None
if 'meta' not in st.session_state: st.session_state.meta = {}

# 🖥️ الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    search = st.text_input("🔍 بحث عن أصل", "")
    filtered = {k:v for k,v in ASSETS_DB.items() if not search or search.lower() in k.lower() or search.lower() in v.lower()}
    selected_name = st.selectbox("الأصل", list(filtered.keys()) if filtered else list(ASSETS_DB.keys()))
    symbol = filtered.get(selected_name, ASSETS_DB[selected_name])
    
    use_custom = st.checkbox("📝 رمز مخصص")
    if use_custom: symbol = st.text_input("الرمز", symbol).strip().upper()
    
    period = st.selectbox("المدة", ["1mo", "3mo", "6mo", "1y"], index=2)
    interval = st.selectbox("الإطار", ["1d", "4h", "1h", "15m"], index=0)
    
    if st.button("🔄 جلب البيانات وتحديث", type="primary"):
        with st.spinner("⏳ جاري الاتصال بالبورصة..."):
            try:
                df_raw = yf.download(symbol, period=period, interval=interval, progress=False)
                if df_raw.empty: st.error("❌ بيانات فارغة."); st.stop()
                if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.droplevel(1)
                st.session_state.df = calc_indicators(df_raw)
                st.session_state.meta = {"symbol": symbol, "interval": interval, "name": selected_name if not use_custom else symbol}
                st.success("✅ تم تحديث البيانات بنجاح!")
            except Exception as e: st.error(f"❌ فشل الجلب: {e}")
    
    st.divider()
    st.subheader("🎛️ المؤشرات (تفاعل فوري)")
    show_gann = st.checkbox("📐 زوايا Gann", True)
    show_smc = st.checkbox(" مناطق SMC/ICT", True)
    show_elliott = st.checkbox("🌊 موجات Elliott", False)
    show_macd = st.checkbox("📉 مؤشر MACD", False)

# 🚀 المنطق الرئيسي
if st.session_state.df is not None:
    df = st.session_state.df
    meta = st.session_state.meta
    direction, score, price, sl, tp1, tp2, tp3 = get_ai_signal(df)
    
    is_buy = "شراء" in direction
    css_class = "signal-box" if is_buy else "signal-box signal-sell"
    
    # 📊 عرض ملخص الإشارة الذكي (محدّث)
    st.markdown(f"""
    <div class="{css_class}">
        <h3 style="margin:0;"> توصية الذكاء الاصطناعي: {direction} (قوة: {score}/100)</h3>
        <p style="margin:8px 0 5px; color:#ccc;">📍 سعر الدخول الحالي: <b>{price:.2f}</b></p>
        <p style="margin:0 0 8px; color:#ff6b6b; font-weight:bold;">🛑 وقف الخسارة (Max 200pt): <b>{sl:.2f}</b></p>
        <div style="margin-top:5px;">
            <span style="color:#aaa; font-size:0.9rem;">🎯 أهداف جني الأرباح (مجموع 500 نقطة):</span><br>
            <span class="tp-stage" style="color:#4cd137;">المرحلة 1: {tp1:.2f} (+150)</span>
            <span class="tp-stage" style="color:#fbc531;">المرحلة 2: {tp2:.2f} (+300)</span>
            <span class="tp-stage" style="color:#e84118;">المرحلة 3: {tp3:.2f} (+500)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    #  بناء الشارت الديناميكي
    rows, heights = (3, [0.5, 0.2, 0.3]) if show_macd else (2, [0.7, 0.3])
    titles = ("السعر", "MACD", "الحجم") if show_macd else ("السعر", "RSI")
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                        row_heights=heights, subplot_titles=titles)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="سعر"), row=1, col=1)
    
    if show_gann:
        rng = df['High'].max() - df['Low'].min()
        gann = df['Low'].min() + np.arange(len(df)) * (rng/len(df))
        fig.add_trace(go.Scatter(x=df.index, y=gann, mode="lines", name="Gann 1x1", line=dict(color="purple", dash="dash", width=2)), row=1, col=1)
        
    if show_smc:
        for i in range(2, len(df)):
            if float(df['Low'].iloc[i]) > float(df['High'].iloc[i-2]):
                fig.add_shape(type="rect", xref="x", yref="y", x0=df.index[i-2], y0=float(df['High'].iloc[i-2]),
                              x1=df.index[i], y1=float(df['Low'].iloc[i]), fillcolor="rgba(0,255,0,0.15)", line=dict(width=0), layer="below", row=1, col=1)
                
    if show_elliott:
        peaks = df[(df['High']==df['High'].rolling(5,center=True).max()) & (df['High'].diff()>0)]
        troughs = df[(df['Low']==df['Low'].rolling(5,center=True).min()) & (df['Low'].diff()<0)]
        fig.add_trace(go.Scatter(x=peaks.index, y=peaks['High'], mode="markers", name="قمم", marker=dict(color="red", symbol="triangle-down", size=10)), row=1, col=1)
        fig.add_trace(go.Scatter(x=troughs.index, y=troughs['Low'], mode="markers", name="قيعان", marker=dict(color="blue", symbol="triangle-up", size=10)), row=1, col=1)

    rsi_row = 2 if not show_macd else 3
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode="lines", name="RSI", line=dict(color="cyan")), row=rsi_row, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=rsi_row, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=rsi_row, col=1)
    
    if show_macd:
        hist = df['MACD'] - df['MACD_Signal']
        colors = ['green' if x>0 else 'red' for x in hist]
        fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], mode="lines", name="MACD", line=dict(color="blue")), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], mode="lines", name="Signal", line=dict(color="orange")), row=2, col=1)
        
    vol_row = rows
    if 'Volume' in df.columns:
        v_colors = ['#26a69a' if c>=o else '#ef5350' for c,o in zip(df['Close'], df['Open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=v_colors), row=vol_row, col=1)
        
    fig.update_layout(height=750, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # 📑 التبويبات
    tab_risk, tab_matrix, tab_export = st.tabs(["🛡️ إدارة المخاطر", "📡 مصفوفة الأطر", "💾 تصدير"])
    
    with tab_risk:
        st.subheader("🛡️ حاسبة إدارة رأس المال (بناءً على SL=200 نقطة)")
        c1, c2 = st.columns(2)
        capital = c1.number_input("💰 رأس المال ($)", min_value=100.0, value=1000.0, step=100.0)
        risk_pct = c2.slider("⚖️ نسبة المخاطرة لكل صفقة (%)", 0.5, 5.0, 1.0, step=0.1)
        
        sl_dist = 200 # ثابت حسب طلبك
        risk_amount = capital * (risk_pct / 100)
        position_size = risk_amount / sl_dist if sl_dist > 0 else 0
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("📦 حجم الصفقة", f"{position_size:.3f} وحدة")
        col_b.metric("💸 مبلغ المخاطرة", f"${risk_amount:.2f}")
        col_c.metric("📊 العائد عند TP3", f"{(500/sl_dist):.2f}R")

    with tab_matrix:
        st.subheader(" توافق الإشارات عبر الأطر الزمنية")
        tf_data = []
        for tf in ["15m", "1h", "4h", "1d"]:
            try:
                d = yf.download(meta['symbol'], period="1mo", interval=tf, progress=False)
                if d.empty or len(d) < 20: continue
                if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
                d = calc_indicators(d)
                _, sc, _, _, _, _, _ = get_ai_signal(d)
                sig = "شراء 🟢" if sc>=60 else "بيع 🔴" if sc<=40 else "محايد ⚪"
                tf_data.append({"الإطار": tf, "التقييم": f"{sc}/100", "الاتجاه": sig})
            except: pass
        if tf_data: st.dataframe(pd.DataFrame(tf_data), use_container_width=True, hide_index=True)
        else: st.info("لا تتوفر بيانات كافية حالياً.")

    with tab_export:
        csv = df.to_csv().encode('utf-8')
        st.download_button(" تحميل البيانات (CSV)", csv, f"{meta['symbol']}_data.csv", "text/csv")
        st.download_button("🖼️ تحميل الشارت (HTML)", fig.to_html(include_plotlyjs='cdn'), f"{meta['symbol']}_chart.html", "text/html")

else:
    st.info(" اختر الأصل من القائمة الجانبية ثم اضغط  جلب البيانات لتحديث الشارت.")
