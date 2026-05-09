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

def prepare_chart_data(df, timeframe):
    """تحويل بيانات pandas إلى صيغة تفهمها مكتبة TradingView بدقة"""
    chart_data = []
    fmt = '%Y-%m-%d' if 'd' in timeframe else '%Y-%m-%d %H:%M'
    
    for idx, row in df.iterrows():
        chart_data.append({
            'time': idx.strftime(fmt),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        })
    return chart_data

def analyze_indicators(df, timeframe, show_gann, show_smc, show_elliott):
    fmt = '%Y-%m-%d' if 'd' in timeframe else '%Y-%m-%d %H:%M'
    results = {'gann': [], 'fvg': [], 'elliott': []}
    
    # 1. Gann Angles
    if show_gann:
        high, low = df['High'].max(), df['Low'].min()
        rng = high - low
        n = len(df)
        for idx in df.index:
            i = df.index.get_loc(idx)
            results['gann'].append({
                'time': idx.strftime(fmt),
                'value': float(low + i * (rng/n))
            })
            
    # 2. SMC Fair Value Gaps
    if show_smc:
        for i in range(2, len(df)):
            if df['Low'].iloc[i] > df['High'].iloc[i-2]:
                results['fvg'].append({
                    'time': df.index[i].strftime(fmt),
                    'top': float(df['High'].iloc[i-2]),
                    'bottom': float(df['Low'].iloc[i])
                })
                
    # 3. Elliott Peaks/Troughs
    if show_elliott:
        peaks = df[df['High'] == df['High'].rolling(5, center=True).max()]
        troughs = df[df['Low'] == df['Low'].rolling(5, center=True).min()]
        
        for idx in peaks.index:
            results['elliott'].append({
                'time': idx.strftime(fmt), 'position': 'aboveBar',
                'color': '#ef5350', 'shape': 'arrowDown', 'text': 'P'
            })
        for idx in troughs.index:
            results['elliott'].append({
                'time': idx.strftime(fmt), 'position': 'belowBar',
                'color': '#26a69a', 'shape': 'arrowUp', 'text': 'T'
            })
            
    return results

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
        st.session_state['run'] = True

if st.session_state.get('run'):
    with st.spinner("جاري جلب البيانات ومعالجتها..."):
        try:
            # ✅ الطريقة الأضمن لجلب البيانات من Yahoo Finance
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo", interval=timeframe)
            
            if df.empty:
                st.error("️ لا توجد بيانات. جرب رمزاً آخر أو إطاراً زمنياً أطول (مثل 1d).")
                st.stop()
                
            # التأكد من وجود الأعمدة الأساسية
            required = ['Open', 'High', 'Low', 'Close']
            if not all(c in df.columns for c in required):
                st.error("❌ تنسيق البيانات غير مدعوم لهذا الرمز.")
                st.stop()
                
            # إزالة الصفوف الفارغة بحذر (فقط إذا كانت الأسعار ناقصة)
            df = df.dropna(subset=required)
            if len(df) < 10:
                st.error("⚠️ بيانات غير كافية للرسم. جرب فترة أطول.")
                st.stop()
                
            # تجهيز الحزم للواجهة
            candles = prepare_chart_data(df, timeframe)
            indicators = analyze_indicators(df, timeframe, show_gann, show_smc, show_elliott)
            
            payload = {
                'candles': candles,
                'indicators': indicators,
                'options': {'gann': show_gann, 'smc': show_smc, 'elliott': show_elliott}
            }
            st.session_state['chart_data'] = json.dumps(payload)
            st.session_state['last_symbol'] = symbol
            del st.session_state['run']
            
        except Exception as e:
            st.error(f"❌ فشل الاتصال: {str(e)}")
            st.info("💡 نصيحة: جرب BTC-USD أو ^GSPC للتأكد من عمل المنصة.")

if 'chart_data' in st.session_state:
    data_json = st.session_state['chart_data']
    
    tv_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #131722; overflow: hidden; }}
            #chart-container {{ width: 100%; height: 82vh; }}
            .hud {{ position: absolute; top: 12px; left: 12px; z-index: 10; 
                   background: rgba(19, 23, 34, 0.95); padding: 8px 14px; border-radius: 6px; 
                   border: 1px solid #2a2e39; color: #d1d4dc; font-family: -apple-system, sans-serif; font-size: 13px; }}
            .price {{ font-weight: bold; color: #2962ff; font-size: 15px; margin-left: 8px; }}
        </style>
    </head>
    <body>
        <div class="hud">📊 <span id="sym">{st.session_state.get('last_symbol', '')}</span> | السعر: <span id="price" class="price">---</span></div>
        <div id="chart-container"></div>
        <script>
            const data = {data_json};
            const container = document.getElementById('chart-container');
            
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: '#1f2943' }}, horzLines: {{ color: '#1f2943' }} }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '#2B2B43' }},
                handleScroll: {{ vertTouchDrag: false }},
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a', downColor: '#ef5350',
                borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            }});
            candleSeries.setData(data.candles);

            if (data.options.gann && data.indicators.gann.length > 0) {{
                const gannSeries = chart.addLineSeries({{ color: '#a044ff', lineWidth: 1, lineStyle: 2 }});
                gannSeries.setData(data.indicators.gann);
            }}

            if (data.options.elliott && data.indicators.elliott.length > 0) {{
                candleSeries.setMarkers(data.indicators.elliott);
            }}

            chart.subscribeCrosshairMove(param => {{
                if (param.time && param.seriesData.has(candleSeries)) {{
                    const d = param.seriesData.get(candleSeries);
                    document.getElementById('price').textContent = d.close.toFixed(2);
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
    st.success("✅ تم تحميل شارت TradingView بنجاح. استخدم العجلة للتكبير والسحب للتحريك.")
else:
    st.info("👈 اختر الأصل والإطار الزمني، ثم اضغط '🔄 تحديث الشارت' للبدء.")
