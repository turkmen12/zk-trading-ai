import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="ProTrader TV Replica", layout="wide", page_icon="📈")

# قاعدة الأصول
ASSETS_DB = {
    "الذهب (Gold)": "GC=F", "الفضة (Silver)": "SI=F", "النفط (Oil)": "CL=F",
    "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD", "EUR/USD": "EURUSD=X", "Tesla": "TSLA"
}

#  دوال التحليل (بايثون)
def analyze_data(df):
    # حساب المؤشرات
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    # Gann (زوايا مبسطة)
    high, low = df['High'].max(), df['Low'].min()
    rng = high - low
    df['Gann_Up'] = low + np.arange(len(df)) * (rng/len(df))
    df['Gann_Down'] = high - np.arange(len(df)) * (rng/len(df))
    
    # SMC (Fair Value Gaps)
    fvg = []
    for i in range(2, len(df)):
        if df['Low'].iloc[i] > df['High'].iloc[i-2]: # Bullish FVG
            fvg.append({'start_idx': i-2, 'end_idx': i, 'top': df['High'].iloc[i-2], 'bottom': df['Low'].iloc[i], 'type': 'bull'})
    
    # Elliott (Peaks/Troughs)
    peaks = df[df['High'] == df['High'].rolling(5, center=True).max()]
    troughs = df[df['Low'] == df['Low'].rolling(5, center=True).min()]
    
    return df, fvg, peaks, troughs

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    asset = st.selectbox("الرمز", ASSETS_DB.keys())
    symbol = ASSETS_DB[asset]
    
    timeframe = st.selectbox("الإطار الزمني", ["1d", "4h", "1h", "15m"])
    
    st.subheader("التحليلات")
    show_gann = st.checkbox("زوايا Gann", True)
    show_smc = st.checkbox("مناطق SMC/ICT", True)
    show_elliott = st.checkbox("موجات Elliott", False)
    
    if st.button("🔄 تحديث الشارت", type="primary"):
        st.session_state['refresh'] = True

# المنطق الرئيسي
if 'refresh' in st.session_state:
    with st.spinner("جاري جلب البيانات..."):
        df = yf.download(symbol, period="6mo", interval=timeframe, progress=False)
        if df.empty:
            st.error("لا توجد بيانات")
            st.stop()
        
        # تحويل البيانات لصيغة TradingView (JSON)
        chart_data = []
        for index, row in df.iterrows():
            time_str = index.strftime('%Y-%m-%d') if 'd' in timeframe else index.strftime('%Y-%m-%d %H:%M')
            chart_data.append({
                'time': time_str,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close'])
            })

        # تجهيز بيانات التحليل
        df_analyzed, fvg_list, peaks, troughs = analyze_data(df)
        
        # تجهيز خطوط Gann
        gann_data = []
        if show_gann:
            for index, row in df_analyzed.iterrows():
                time_str = index.strftime('%Y-%m-%d') if 'd' in timeframe else index.strftime('%Y-%m-%d %H:%M')
                gann_data.append({
                    'time': time_str,
                    'gann_up': float(row['Gann_Up']),
                    'gann_down': float(row['Gann_Down'])
                })

        # تجهيز Elliott Points
        elliott_points = []
        if show_elliott:
            for idx in peaks.index:
                time_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M')
                elliott_points.append({'time': time_str, 'price': float(peaks.loc[idx, 'High']), 'text': 'Peak', 'color': 'red', 'shape': 'arrowDown'})
            for idx in troughs.index:
                time_str = idx.strftime('%Y-%m-%d') if 'd' in timeframe else idx.strftime('%Y-%m-%d %H:%M')
                elliott_points.append({'time': time_str, 'price': float(troughs.loc[idx, 'Low']), 'text': 'Trough', 'color': 'blue', 'shape': 'arrowUp'})

        # حزم البيانات للواجهة
        payload = {
            'candles': chart_data,
            'gann': gann_data,
            'fvg': [{'start': d['start_idx'], 'end': d['end_idx'], 'top': d['top'], 'bottom': d['bottom']} for d in fvg_list],
            'elliott': elliott_points,
            'options': {
                'gann': show_gann,
                'smc': show_smc,
                'elliott': show_elliott
            }
        }
        st.session_state['chart_payload'] = json.dumps(payload)
        del st.session_state['refresh']

# واجهة عرض الشارت
if 'chart_payload' in st.session_state:
    payload = st.session_state['chart_payload']
    
    # كود HTML/JS الخاص بـ TradingView
    tv_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #131722; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
            #chart-container {{ width: 100%; height: 85vh; }}
            .price-display {{ position: absolute; top: 20px; right: 20px; z-index: 10; background: #1e222d; padding: 10px 20px; border-radius: 4px; border: 1px solid #2a2e39; color: #d1d4dc; }}
            .price-val {{ font-size: 24px; font-weight: bold; color: #2962ff; }}
        </style>
    </head>
    <body>
        <div class="price-display">السعر الحالي: <span id="current-price" class="price-val">...</span></div>
        <div id="chart-container"></div>
        <script>
            const data = {payload};
            const chartContainer = document.getElementById('chart-container');
            
            // إعداد الشارت
            const chart = LightweightCharts.createChart(chartContainer, {{
                width: chartContainer.clientWidth,
                height: chartContainer.clientHeight,
                layout: {{
                    background: {{ color: '#131722' }},
                    textColor: '#d1d4dc',
                }},
                grid: {{
                    vertLines: {{ color: '#1f2943' }},
                    horzLines: {{ color: '#1f2943' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                timeScale: {{
                    borderColor: '#2B2B43',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            // إضافة الشموع
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350',
            }});
            candleSeries.setData(data.candles);

            // إضافة Gann
            if (data.options.gann) {{
                const gannSeries = chart.addLineSeries({{ color: '#a044ff', lineWidth: 1, priceLineVisible: false }});
                const gannData = data.gann.map(d => ({{ time: d.time, value: d.gann_up }}));
                gannSeries.setData(gannData);
            }}

            // إضافة Elliott Markers
            if (data.options.elliott) {{
                candleSeries.setMarkers(data.elliott);
            }}

            // تحديث السعر عند تحريك الماوس
            chart.subscribeCrosshairMove(param => {{
                if (param.time && param.seriesData.size > 0) {{
                    const price = param.seriesData.get(candleSeries).close;
                    document.getElementById('current-price').textContent = price;
                }}
            }});

            // ضبط الحجم عند تغيير النافذة
            window.addEventListener('resize', () => {{
                chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
            }});
        </script>
    </body>
    </html>
    """
    
    st.components.v1.html(tv_html, height=900, scrolling=False)
    
    # معلومات إضافية أسفل الشارت
    st.markdown("---")
    st.info(" هذا الشارت يعمل بمحرك TradingView الحقيقي. استخدم عجلة الماوس للتكبير، واسحب للتحريك.")

else:
    st.info("👈 اختر الأصل والإطار الزمني، ثم اضغط 'تحديث الشارت' لبدء العرض.")
