import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 🎨 إعدادات الواجهة
st.set_page_config(page_title="ProTrader AI", layout="wide", page_icon="📈")
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button {font-size: 14px; font-weight: 600; padding: 8px 16px;}
    .signal-box {background: #0e1117; border-left: 4px solid #00ff00; padding: 15px; border-radius: 8px; margin: 10px 0;}
    .signal-sell {border-left-color: #ff4444;}
    .tp-stage {display: inline-block; background: #1a1d24; padding: 6px 12px; margin: 4px; border-radius: 6px; font-weight: bold; font-size: 0.9rem;}
    .metric-card {background: #1a1d24; border-radius: 10px; padding: 15px; text-align: center;}
    .info-pill {background: #262730; padding: 5px 12px; border-radius: 15px; font-size: 0.85rem; color: #ddd;}
    .elliott-status {padding: 10px; border-radius: 8px; margin: 10px 0; font-weight: bold;}
    .elliott-valid {background: rgba(0,255,0,0.1); border: 1px solid #00ff00; color: #00ff00;}
    .elliott-warn {background: rgba(255,165,0,0.1); border: 1px solid #ffa500; color: #ffa500;}
    .elliott-invalid {background: rgba(255,0,0,0.1); border: 1px solid #ff4444; color: #ff4444;}
</style>
""", unsafe_allow_html=True)

# 📦 قاعدة الأصول
ASSETS_DB = {
    "🥇 الذهب (Gold)": "GC=F", "🥈 الفضة (Silver)": "SI=F", "🛢️ النفط (Oil)": "CL=F",
    "📈 S&P 500": "^GSPC", " Nasdaq": "^IXIC", "🇬🇧 FTSE 100": "^FTSE",
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

def get_pip_size(price):
    if price > 5000: return 1.0
    elif price > 50: return 0.1
    else: return 0.0001

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
    
    pip_size = get_pip_size(price)
    SL_PIPS = 200
    TP1_PIPS, TP2_PIPS, TP3_PIPS = 150, 300, 500
    
    sl = price - (SL_PIPS * pip_size * mult)
    tp1 = price + (TP1_PIPS * pip_size * mult)
    tp2 = price + (TP2_PIPS * pip_size * mult)
    tp3 = price + (TP3_PIPS * pip_size * mult)
    
    return direction, score, price, sl, tp1, tp2, tp3, pip_size, SL_PIPS

# 🌊 محرك موجات إليوت الذكي
def detect_elliott_waves(df, sensitivity=0.015):
    # إيجاد القمم والقيعان المهمة
    highs = df['High'].rolling(window=5, center=True).max()
    lows = df['Low'].rolling(window=5, center=True).min()
    
    peaks = df[df['High'] == highs][['High']].drop_duplicates()
    troughs = df[df['Low'] == lows][['Low']].drop_duplicates()
    
    swings = []
    for idx, row in peaks.iterrows(): swings.append(('peak', idx, float(row['High'])))
    for idx, row in troughs.iterrows(): swings.append(('trough', idx, float(row['Low'])))
    swings.sort(key=lambda x: x[1])
    
    # تصفية التقلبات الصغيرة
    filtered = []
    last = None
    for t, idx, p in swings:
        if last is None or abs(p - last)/max(abs(last), 1) > sensitivity:
            filtered.append((t, idx, p))
            last = p
            
    if len(filtered) < 6:
        return [], "بيانات غير كافية للعد"

    # البحث عن نمط 1-2-3-4-5 صاعد (الأكثر شيوعاً)
    labels = []
    status = "️ قيد التشكل أو غير مكتمل"
    css = "elliott-warn"
    
    for i in range(len(filtered) - 5):
        if filtered[i][0] != 'trough': continue # البداية يجب أن تكون قاعاً
        
        w1_start = filtered[i]
        w1_end = next((s for s in filtered[i:] if s[0]=='peak'), None)
        if not w1_end: continue
        
        w2_end = next((s for s in filtered if s[1]>w1_end[1] and s[0]=='trough' and s[2] > w1_start[2]), None)
        if not w2_end: continue
        
        w3_end = next((s for s in filtered if s[1]>w2_end[1] and s[0]=='peak' and s[2] > w1_end[2]), None)
        if not w3_end: continue
        
        w4_end = next((s for s in filtered if s[1]>w3_end[1] and s[0]=='trough' and s[2] > w2_end[2] and s[2] < w1_end[2]), None)
        if not w4_end: continue
        
        w5_end = next((s for s in filtered if s[1]>w4_end[1] and s[0]=='peak' and s[2] > w3_end[2]), None)
        if not w5_end: continue
        
        # التحقق من القواعد الصارمة
        len1 = w1_end[2] - w1_start[2]
        len2 = w1_end[2] - w2_end[2]
        len3 = w3_end[2] - w2_end[2]
        len5 = w5_end[2] - w4_end[2]
        
        valid = True
        reason = ""
        if len2 > len1: valid=False; reason="الموجة 2 اخترقت بداية الموجة 1"
        elif len3 < len1 and len3 < len5: valid=False; reason="الموجة 3 هي الأقصر"
        elif w4_end[2] < w1_end[2]: valid=False; reason="الموجة 4 تداخلت مع نطاق الموجة 1"
        
        if valid:
            labels = [
                ('trough', w1_start[1], w1_start[2], '1'),
                ('peak', w1_end[1], w1_end[2], '2'),
                ('trough', w2_end[1], w2_end[2], '3'), # تصحيح: الموجة 3 نهاية عند قمة
                ('peak', w3_end[1], w3_end[2], '4'),   # تصحيح: الموجة 4 نهاية عند قاع
                ('trough', w4_end[1], w4_end[2], '5'), # تصحيح: الموجة 5 نهاية عند قمة
            ]
            # إعادة ترتيب التسميات بشكل صحيح للعرض
            labels = [
                (w1_start[1], w1_start[2], '1 Start'),
                (w1_end[1], w1_end[2], '1'),
                (w2_end[1], w2_end[2], '2'),
                (w3_end[1], w3_end[2], '3'),
                (w4_end[1], w4_end[2], '4'),
                (w5_end[1], w5_end[2], '5')
            ]
            
            # البحث عن ABC تصحيحية
            a_end = next((s for s in filtered if s[1]>w5_end[1] and s[0]=='trough'), None)
            b_end = next((s for s in filtered if s[1]>a_end[1] and s[0]=='peak' and s[2] < w5_end[2]), None)
            c_end = next((s for s in filtered if s[1]>b_end[1] and s[0]=='trough' and s[2] < a_end[2]), None)
            
            if a_end and b_end and c_end:
                labels.extend([(a_end[1], a_end[2], 'A'), (b_end[1], b_end[2], 'B'), (c_end[1], c_end[2], 'C')])
                status = f"✅ نمط 1-2-3-4-5 + ABC مكتمل وصحيح"
                css = "elliott-valid"
            else:
                status = f"✅ الموجات الدافعة 1-5 صحيحة | التصحيح ABC قيد التشكل"
                css = "elliott-warn"
            break # أخذ أول نمط صحيح
        else:
            status = f"❌ نمط محتمل لكنه مخالف للقاعدة: {reason}"
            css = "elliott-invalid"
            
    return labels, status, css

# 🧠 إدارة الحالة
if 'df' not in st.session_state: st.session_state.df = None
if 'meta' not in st.session_state: st.session_state.meta = {}

# 🖥️ الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    search = st.text_input(" بحث عن أصل", "")
    filtered = {k:v for k,v in ASSETS_DB.items() if not search or search.lower() in k.lower() or search.lower() in v.lower()}
    selected_name = st.selectbox("الأصل", list(filtered.keys()) if filtered else list(ASSETS_DB.keys()))
    symbol = filtered.get(selected_name, ASSETS_DB[selected_name])
    
    use_custom = st.checkbox("📝 رمز مخصص")
    if use_custom: symbol = st.text_input("الرمز", symbol).strip().upper()
    
    period = st.selectbox("المدة", ["1mo", "3mo", "6mo", "1y"], index=2)
    interval = st.selectbox("الإطار", ["1d", "4h", "1h", "15m"], index=0)
    
    if st.button(" جلب البيانات وتحديث", type="primary"):
        with st.spinner("⏳ جاري الاتصال بالبورصة..."):
            try:
                df_raw = yf.download(symbol, period=period, interval=interval, progress=False)
                if df_raw.empty: st.error("❌ بيانات فارغة."); st.stop()
                if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.droplevel(1)
                st.session_state.df = calc_indicators(df_raw)
                st.session_state.meta = {"symbol": symbol, "interval": interval, "name": selected_name if not use_custom else symbol}
                st.success("✅ تم تحديث البيانات!")
            except Exception as e: st.error(f"❌ فشل الجلب: {e}")
    
    st.divider()
    st.subheader("🎛️ المؤشرات (تفاعل فوري)")
    show_gann = st.checkbox(" زوايا Gann", True)
    show_smc = st.checkbox("🏦 مناطق SMC/ICT", True)
    show_elliott = st.checkbox("🌊 موجات Elliott (1-5 + ABC)", False)
    show_macd = st.checkbox("📉 مؤشر MACD", False)

# 🚀 المنطق الرئيسي
if st.session_state.df is not None:
    df = st.session_state.df
    meta = st.session_state.meta
    direction, score, price, sl, tp1, tp2, tp3, pip_size, SL_PIPS = get_ai_signal(df)
    
    is_buy = "شراء" in direction
    css_class = "signal-box" if is_buy else "signal-box signal-sell"
    dec = 4 if pip_size < 0.01 else 2
    
    st.markdown(f"""
    <div class="{css_class}">
        <h3 style="margin:0; font-size:1.3rem;"> توصية النظام: {direction} (قوة: {score}/100)</h3>
        <div style="margin:10px 0; display:flex; gap:10px; flex-wrap:wrap;">
            <span class="info-pill"> الدخول: <b>{price:.{dec}f}</b></span>
            <span class="info-pill" style="color:#ff6b6b; border:1px solid #ff6b6b;">🛑 وقف خسارة {SL_PIPS} بيب: <b>{sl:.{dec}f}</b></span>
        </div>
        <div style="margin-top:8px;">
            <span style="color:#aaa; font-size:0.85rem;">🎯 أهداف جني الأرباح (إجمالي 500 بيب):</span><br>
            <span class="tp-stage" style="color:#4cd137;">المرحلة 1: {tp1:.{dec}f} (+150 بيب)</span>
            <span class="tp-stage" style="color:#fbc531;">المرحلة 2: {tp2:.{dec}f} (+300 بيب)</span>
            <span class="tp-stage" style="color:#e84118;">المرحلة 3: {tp3:.{dec}f} (+500 بيب)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # بناء الشارت
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
        labels, status, css = detect_elliott_waves(df)
        st.markdown(f'<div class="elliott-status {css}">{status}</div>', unsafe_allow_html=True)
        
        if labels:
            idxs = [l[0] for l in labels]
            prices = [l[1] for l in labels]
            texts = [l[2] for l in labels]
            # وضع الأرقام فوق القمم وتحت القيعان لمنع التداخل
            positions = ['top' if df.loc[i, 'High'] == p else 'bottom' for i, p in zip(idxs, prices)]
            fig.add_trace(go.Scatter(x=idxs, y=prices, mode="markers+text", text=texts, 
                                     textposition=positions, textfont=dict(size=14, color="white", family="Arial Black"),
                                     marker=dict(color="#FFD700", size=12, line=dict(width=2, color="black")),
                                     name="Elliott Waves", hoverinfo="text"), row=1, col=1)

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

    tab_risk, tab_matrix, tab_export = st.tabs(["️ إدارة المخاطر", "📡 مصفوفة الأطر", "💾 تصدير"])
    
    with tab_risk:
        st.subheader("🛡️ حاسبة إدارة رأس المال (معيارية)")
        c1, c2, c3 = st.columns(3)
        lot_size = c1.number_input("📦 حجم اللوت", min_value=0.01, value=0.01, step=0.01)
        risk_per_pip_std = 10.0
        total_risk_usd = lot_size * SL_PIPS * risk_per_pip_std
        potential_profit_usd = lot_size * 500 * risk_per_pip_std
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("💸 مخاطرة الصفقة (SL)", f"${total_risk_usd:.2f}")
        col_b.metric("💰 ربح الصفقة الكامل (TP3)", f"${potential_profit_usd:.2f}")
        col_c.metric(" نسبة العائد للمخاطرة", f"{500/SL_PIPS:.1f}R")
        st.caption(f" المعادلة: اللوت ({lot_size}) × البييبات ({SL_PIPS}) × القيمة ($10) = ${total_risk_usd:.2f}")

        with tab_matrix:
        st.subheader("📡 توافق الإشارات عبر الأطر")
        tf_data = []
        for tf in ["15m", "1h", "4h", "1d"]:
            try:
                d = yf.download(meta['symbol'], period="1mo", interval=tf, progress=False)
                if d.empty or len(d) < 20: continue
                if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
                d = calc_indicators(d)
                _, sc, _, _, _, _, _, _, _ = get_ai_signal(d)
                sig = "شراء 🟢" if sc>=60 else "بيع 🔴" if sc<=40 else "محايد ⚪"
                tf_data.append({"الإطار": tf, "التقييم": f"{sc}/100", "الاتجاه": sig})
            except: pass
        if len(tf_data) > 0:
            st.dataframe(pd.DataFrame(tf_data), use_container_width=True, hide_index=True)
        else:
            st.info("لا تتوفر بيانات كافية حالياً.")
