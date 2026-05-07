import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

st.set_page_config(page_title="منصة التحليل الذكي المتقدمة", layout="wide", page_icon="📈")
st.title("📊 منصة التحليل الفني المتكاملة")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ إعدادات التحليل")
    symbol = st.text_input("رمز الأصل (مثال: BTC-USD, AAPL)", "BTC-USD")
    period = st.selectbox("المدة الزمنية", ["1mo", "3mo", "6mo", "1y"], index=2)
    interval = st.selectbox("الإطار الزمني", ["1d", "4h", "1h", "15m"], index=0)
    
    st.subheader("تفعيل المدارس التحليلية")
    show_gann = st.checkbox("📐 زوايا Gann", value=True)
    show_smc = st.checkbox("🏦 مناطق SMC/ICT", value=True)
    show_elliott = st.checkbox("🌊 موجات Elliott", value=False)

def get_scalar_value(series):
    """دالة مساعدة لاستخراج قيمة رقمية واحدة بأمان"""
    if hasattr(series, 'iloc'):
        val = series.iloc[-1]
        if hasattr(val, 'item'):
            return float(val.item())
        return float(val)
    return float(series)

if st.sidebar.button("🔍 تحليل السوق الآن"):
    with st.spinner('جاري جلب البيانات...'):
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            
            if df.empty:
                st.error("⚠️ لم يتم العثور على بيانات.")
                st.stop()
            
            # التأكد من وجود الأعمدة بشكل صحيح
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            
            # حساب المؤشرات
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            # استخراج القيم باستخدام الدالة الآمنة
            last_price = get_scalar_value(df['Close'])
            last_rsi = get_scalar_value(df['RSI']) if not pd.isna(df['RSI'].iloc[-1]) else 50.0
            last_sma = get_scalar_value(df['SMA_50']) if not pd.isna(df['SMA_50'].iloc[-1]) else 0.0
            
            # منطق التقييم
            score = 50
            if last_rsi < 30: score += 20
            elif last_rsi > 70: score -= 20
            
            if last_sma > 0 and last_price > last_sma: score += 15
            elif last_sma > 0 and last_price < last_sma: score -= 15
            
            if score >= 70: signal, color = "شراء قوي 🟢", "green"
            elif score >= 55: signal, color = "شراء محتمل 🟢", "lightgreen"
            elif score <= 30: signal, color = "بيع قوي 🔴", "red"
            elif score <= 45: signal, color = "بيع محتمل 🔴", "orange"
            else: signal, color = "انتظار ⚪", "gray"

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 السعر", f"${last_price:.2f}")
            col2.metric("📊 RSI", f"{last_rsi:.1f}")
            col3.metric("🤖 التقييم", f"{score}/100")
            col4.markdown(f"<h3 style='color:{color}; text-align:center;'>{signal}</h3>", unsafe_allow_html=True)

            # بناء الشارت
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, row_heights=[0.7, 0.3])

            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                         low=df['Low'], close=df['Close'], name="السعر"), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], mode='lines', name='SMA 50', 
                                     line=dict(color='yellow', width=1)), row=1, col=1)

            if show_gann:
                high, low = df['High'].max(), df['Low'].min()
                rng = high - low
                n = len(df)
                gann_line = low + np.arange(n) * (rng/n)
                fig.add_trace(go.Scatter(x=df.index, y=gann_line, mode="lines", 
                                         name="Gann 1x1", line=dict(color="purple", dash="dash")), row=1, col=1)

            if show_smc:
                for i in range(2, len(df)):
                    try:
                        if float(df['Low'].iloc[i]) > float(df['High'].iloc[i-2]):
                            fig.add_shape(type="rect", xref="x", yref="y",
                                x0=df.index[i-2], y0=float(df['High'].iloc[i-2]),
                                x1=df.index[i], y1=float(df['Low'].iloc[i]),
                                fillcolor="rgba(0, 255, 0, 0.2)", line=dict(width=0),
                                layer="below", row=1, col=1)
                    except:
                        pass

            if show_elliott:
                peaks = df[(df['High'] == df['High'].rolling(5, center=True).max()) & (df['High'].diff() > 0)]
                troughs = df[(df['Low'] == df['Low'].rolling(5, center=True).min()) & (df['Low'].diff() < 0)]
                fig.add_trace(go.Scatter(x=peaks.index, y=peaks['High'], mode='markers', name='قمم', 
                                         marker=dict(color='red', symbol='triangle-down', size=10)), row=1, col=1)
                fig.add_trace(go.Scatter(x=troughs.index, y=troughs['Low'], mode='markers', name='قيعان', 
                                         marker=dict(color='blue', symbol='triangle-up', size=10)), row=1, col=1)

            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', 
                                     line=dict(color='cyan')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False,
                             title=f"{symbol} - {interval}")
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"❌ حدث خطأ: {str(e)}")
            st.info("💡 تأكد من صحة الرمز وحاول إطاراً زمنياً مختلفاً")
else:
    st.info("👈 اضبط الإعدادات من القائمة الجانبية واضغط 'تحليل السوق الآن'")
