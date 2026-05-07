import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# إعداد الصفحة
st.set_page_config(page_title="منصة التحليل الذكي المتقدمة", layout="wide", page_icon="")
st.markdown("""
<style>
    .stDataFrame {font-size: 10px;}
    .big-font {font-size:24px !important; font-weight: bold; color: #00ff00;}
</style>
""", unsafe_allow_html=True)

st.title(" منصة التحليل الفني المتكاملة")
st.markdown("---")

# --- الشريط الجانبي للإعدادات ---
with st.sidebar:
    st.header("️ إعدادات التحليل")
    symbol = st.text_input("رمز الأصل (مثال: BTC-USD, AAPL)", "BTC-USD")
    period = st.selectbox("المدة الزمنية", ["1mo", "3mo", "6mo", "1y"], index=2)
    interval = st.selectbox("الإطار الزمني", ["1d", "4h", "1h", "15m"], index=0)
    
    st.subheader("تفعيل المدارس التحليلية")
    show_gann = st.checkbox("📐 زوايا Gann", value=True)
    show_smc = st.checkbox("🏦 مناطق SMC/ICT", value=True)
    show_elliott = st.checkbox("🌊 موجات Elliott", value=False)

if st.sidebar.button(" تحليل السوق الآن"):
    with st.spinner('جاري جلب البيانات وتشغيل المحرك الذكي...'):
        try:
            # جلب البيانات
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            if df.empty:
                st.error("⚠️ لم يتم العثور على بيانات لهذا الرمز.")
                st.stop()
            
            # --- 1. حساب المؤشرات الفنية ---
            # حساب RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # حساب المتوسط المتحرك (لاتجاه)
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            last_price = df['Close'].iloc[-1]
            last_rsi = df['RSI'].iloc[-1]
            last_sma = df['SMA_50'].iloc[-1]
            
            # --- 2. منطق الذكاء الاصطناعي البسيط (Smart Logic) ---
            score = 50 # نقطة انطلاق
            signal = "محايد"
            
            # شرط RSI
            if last_rsi < 30: score += 20 # تشبع بيعي (فرصة شراء)
            elif last_rsi > 70: score -= 20 # تشبع شرائي (خطر بيع)
            
            # شرط الاتجاه
            if not np.isnan(last_sma):
                if last_price > last_sma: score += 15 # اتجاه صاعد
                else: score -= 15 # اتجاه هابط
            
            # تحديد الإشارة النهائية
            if score >= 70: signal, color = "شراء قوي 🟢", "green"
            elif score >= 55: signal, color = "شراء محتمل 🟢", "lightgreen"
            elif score <= 30: signal, color = "بيع قوي 🔴", "red"
            elif score <= 45: signal, color = "بيع محتمل 🔴", "orange"
            else: signal, color = "انتظار ⚪", "gray"

            # --- عرض لوحة البيانات العلوية ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("السعر الحالي", f"${last_price:.2f}")
            col2.metric("مؤشر RSI", f"{last_rsi:.2f}", delta=None if np.isnan(last_rsi) else last_rsi-50)
            col3.metric("تقييم الذكاء الاصطناعي", f"{score}/100", delta=f"{score-50}")
            col4.markdown(f"<h3 style='color:{color}; text-align:center;'>{signal}</h3>", unsafe_allow_html=True)

            # --- 3. بناء الشارت ---
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, row_heights=[0.7, 0.3],
                                subplot_titles=(f'شارت {symbol} - {interval}', 'مؤشر القوة النسبية RSI'))

            # الشموع
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                         low=df['Low'], close=df['Close'], name="السعر"), row=1, col=1)
            
            # المتوسط المتحرك
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='yellow', width=1)), row=1, col=1)

            # --- تطبيق مدارس التحليل المختارة ---
            
            # 1. Gann
            if show_gann:
                high, low = df['High'].max(), df['Low'].min()
                rng = high - low
                n = len(df)
                # زاوية 1x1
                gann_line = low + np.arange(n) * (rng/n)
                fig.add_trace(go.Scatter(x=df.index, y=gann_line, mode="lines", 
                                         name="Gann Support 1x1", line=dict(color="purple", dash="dash")), row=1, col=1)

            # 2. SMC (FVG)
            if show_smc:
                # بحث عن فجوات صاعدة
                for i in range(2, len(df)):
                    if df['Low'].iloc[i] > df['High'].iloc[i-2]: # شرط مبسط للفجوة
                         fig.add_shape(type="rect", xref="x", yref="y",
                            x0=df.index[i-2], y0=df['High'].iloc[i-2],
                            x1=df.index[i], y1=df['Low'].iloc[i],
                            fillcolor="rgba(0, 255, 0, 0.2)", line=dict(width=0),
                            layer="below", row=1, col=1)

            # 3. Elliott (ZigZag بسيط)
            if show_elliott:
                # نستخدم خوارزمية بسيطة للقمم والقيعان
                peaks = df[(df['High'] == df['High'].rolling(5, center=True).max()) & (df['High'].diff() > 0)]
                troughs = df[(df['Low'] == df['Low'].rolling(5, center=True).min()) & (df['Low'].diff() < 0)]
                
                fig.add_trace(go.Scatter(x=peaks.index, y=peaks['High'], mode='markers', name='قمم', 
                                         marker=dict(color='red', symbol='triangle-down', size=10)), row=1, col=1)
                fig.add_trace(go.Scatter(x=troughs.index, y=troughs['Low'], mode='markers', name='قيعان', 
                                         marker=dict(color='blue', symbol='triangle-up', size=10)), row=1, col=1)

            # رسم RSI في الجزء السفلي
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='cyan')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

            # تنسيق الشارت
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"حدث خطأ: {e}")

else:
    st.info("👈 يرجى ضبط الإعدادات من القائمة الجانبية ثم اضغط 'تحليل السوق الآن'.")
