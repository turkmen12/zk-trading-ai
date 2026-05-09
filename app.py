import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ProTrader TV Replica", layout="wide", page_icon="📈")

ASSETS_DB = {
    "الذهب (Gold)": "GC=F", "الفضة (Silver)": "SI=F", "النفط (Oil)": "CL=F",
    "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD", "EUR/USD": "EURUSD=X", "Tesla": "TSLA"
}

def analyze_data(df):
    df = df.copy()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    high, low = df['High'].max(), df['Low'].min()
    rng = high - low
    n = len(df)
    df['Gann_Up'] = low + np.arange(n) * (rng/n)
    df['Gann_Down'] = high - np.arange(n) * (rng/n)
    
    # SMC FVGs
    fvg_list = []
    for i in range(2, len(df)):
        if df['Low'].iloc[i] > df['High'].iloc[i-2]:
            fvg_list.append({
                'time': df.index[i].strftime('%Y-%m-%d') if 'd' in st.session_state.get('tf', '1d') else df.index[i].strftime('%Y-%m-%d %H:%M'),
                'top': float(df['High'].iloc[i-2]),
                'bottom': float(df['Low'].iloc[i])
            })
            
    peaks = df[df['High'] == df['High'].rolling(5, center=True).max()]
    troughs = df[df['Low'] == df['Low'].rolling(5, center=True).min()]
    return df, fvg_list, peaks, troughs

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    asset = st.selectbox("الرمز", ASSETS_DB.keys())
    symbol = ASSETS_DB[asset]
    timeframe = st.selectbox("الإطار الزمني", ["1d", "4h", "1h", "15m"])
    st.session_state['tf'] = timeframe
    
    st.subheader("التحليلات")
    show_gann = st.checkbox("زوايا Gann", True)
    show_smc = st.checkbox("مناطق SMC/ICT", True)
    show_elliott = st.checkbox("موجات Elliott", False)
    
    if st.button("🔄 تحديث الشارت", type="primary"):
        st.session_state['refresh'] = True

if 'refresh' in st.session_state:
    with st.spinner("جاري معالجة البيانات..."):
        try:
            df = yf.download(symbol, period="6mo", interval=timeframe, progress=False)
            if df.empty:
                st.error("لا توجد بيانات متاحة لهذا الرمز/الإطار.")
                st.stop()
                
            # 🔧 إصلاح مشكلة MultiIndex الشائعة في yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # حذف الصفوف الفارغة لتجنب خطأ float()
            df = df.dropna()
            
            # تجهيز بيانات الشموع
            chart_data = []
            for idx, row in df.iterrows():
                t_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M:%S')
                chart_data.append({
                    'time': t_str,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close'])
                })

            df_analyzed, fvg_list, peaks, troughs = analyze_data(df)
            
            # تجهيز Gann (TV Line Series تتوقع {time, value})
            gann_data = []
            if show_gann:
                for idx, row in df_analyzed.iterrows():
                    t_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M:%S')
                    gann_data.append({'time': t_str, 'value': float(row['Gann_Up'])})

            # تجهيز Elliott Markers
            elliott_markers = []
            if show_elliott:
                for idx in peaks.index:
                    t_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M:%S')
                    elliott_markers.append({'time': t_str, 'position': 'aboveBar', 'color': '#ef5350', 'shape': 'arrowDown', 'text': 'P'})
                for idx in troughs.index:
                    t_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M:%S')
                    elliott_markers.append({'time': t_str, 'position': 'belowBar', 'color': '#26a69a', 'shape': 'arrowUp', 'text': 'T'})

            payload = {
                'candles': chart_data,
                'gann': gann_data,
                'fvg': fvg_list,
                'elliott': elliott_markers,
                'options': {'gann': show_gann, 'smc': show_smc, 'elliott': show_elliott}
            }
            st.session_state['chart_payload'] = json.dumps(payload)
            del st.session_state['refresh']
        except Exception as e:
            st.error(f"فشل في جلب البيانات: {e}")

if 'chart_payload' in st.session_state:
    payload = st.session_state['chart_payload']
    
    tv_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #131722; overflow: hidden; }}
            #chart-container {{ width: 100%; height: 80vh; }}
            .info-bar {{ position: absolute; top: 10px; left: 10px; z-index: 10; background: rgba(30,34,45,0.9); padding: 8px 12px; border-radius: 6px; color: #d1d4dc; font-family: sans-serif; font-size: 13px; pointer-events: none; }}
        </style>
    </head>
    <body>
        <div class="info-bar" id="info-bar">السعر: --- | الإطار: {timeframe}</div>
        <div id="chart-container"></div>
        <script>
            const data = {payload};
            const container = document.getElementById('chart-container');
            
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: '#1f2943' }}, horzLines: {{ color: '#1f2943' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '#2B2B43' }},
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a', downColor: '#ef5350',
                borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            }});
            candleSeries.setData(data.candles);

            if (data.options.gann && data.gann.length > 0) {{
                const gannSeries = chart.addLineSeries({{ color: '#a044ff', lineWidth: 1, lineStyle: 2 }});
                gannSeries.setData(data.gann);
            }}

            if (data.options.elliott && data.elliott.length > 0) {{
                candleSeries.setMarkers(data.elliott);
            }}

            // تحديث شريط المعلومات عند تحريك الماوس
            chart.subscribeCrosshairMove(param => {{
                if (param.time) {{
                    const price = param.seriesData.get(candleSeries);
                    if (price) {{
                        document.getElementById('info-bar').textContent = `السعر: ${{price.close.toFixed(2)}} | O: ${{price.open.toFixed(2)}} H: ${{price.high.toFixed(2)}} L: ${{price.low.toFixed(2)}}`;
                    }}
                }}
            }});

            window.addEventListener('resize', () => {{
                chart.resize(container.clientWidth, container.clientHeight);
            }});
        </script>
    </body>
    </html>
    """
    st.components.v1.html(tv_html, height=850, scrolling=False)
    st.success("✅ تم تحميل الشارت بنجاح. استخدم عجلة الماوس للتكبير والسحب للتحريك.")
else:
    st.info("👈 اختر الأصل والإطار الزمني، ثم اضغط '🔄 تحديث الشارت' للبدء.")
