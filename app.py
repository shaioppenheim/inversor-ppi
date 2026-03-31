"""
Dashboard de inversiones — CEDEARs con análisis técnico, fundamental y CCL.
Ejecutar: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import os

load_dotenv()

from modules.ppi_client import get_cartera, PPIClient
from modules.market_data import get_precio_usd, get_ccl_referencia, calcular_ccl_implicito
from modules.technical import analizar_tecnico
from modules.advisor import analizar_cedear, chat_libre
from modules.whatsapp_parser import parsear_chat_whatsapp, ingresar_mensaje_manual
from data.cedears import CEDEARS, CEDEARS_TOP_LIQUIDOS

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Inversor PPI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card { background: #1e1e2e; padding: 16px; border-radius: 8px; margin: 4px 0; }
    .compra { color: #00ff88; font-weight: bold; }
    .venta { color: #ff4466; font-weight: bold; }
    .neutro { color: #ffaa00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Inversor PPI")
    st.caption("CEDEARs · Técnico · Fundamental · CCL")

    seccion = st.radio(
        "Sección",
        ["Mi Cartera", "Analizar CEDEAR", "Oportunidades", "Chat con Asesor", "Mensajes Broker"],
        index=0,
    )

    st.divider()
    usar_demo = not bool(os.getenv("PPI_CLIENT_ID"))
    if usar_demo:
        st.warning("🔒 Sin API PPI\nUsando cartera demo")
        st.caption("Configurar en .env para ver tu cartera real")
    else:
        st.success("✅ PPI conectado")

    ccl = get_ccl_referencia()
    st.metric("CCL actual", f"${ccl:,.0f}")


# ── Estado de sesión ──────────────────────────────────────────────────────────
if "mensajes_broker" not in st.session_state:
    st.session_state.mensajes_broker = []

if "cartera" not in st.session_state:
    with st.spinner("Cargando cartera..."):
        st.session_state.cartera = get_cartera(usar_demo=usar_demo)
    st.session_state.pnl_cargado = False

if "pnl_cargado" not in st.session_state:
    st.session_state.pnl_cargado = False


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN: MI CARTERA
# ══════════════════════════════════════════════════════════════════════════════
if seccion == "Mi Cartera":
    st.header("📋 Mi Cartera")

    cartera = st.session_state.cartera
    if not cartera:
        st.info("No hay posiciones en la cartera.")
        st.stop()

    # Resumen
    total = sum(p.get("valor_total_ars", 0) or 0 for p in cartera.values())
    pnl_usd_total = sum(p.get("pnl_usd", 0) or 0 for p in cartera.values())
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Valor total", f"${total:,.0f}")
    col2.metric("Posiciones", len(cartera))
    col3.metric("CCL", f"${ccl:,.0f}")
    col4.metric("Valor en USD", f"${total/ccl:,.0f}")
    col5.metric("P&L total USD", f"${pnl_usd_total:+,.0f}" if pnl_usd_total else "—")

    # Cargar P&L real desde historial de movimientos
    if not usar_demo and not st.session_state.pnl_cargado:
        if st.button("📊 Calcular precio promedio y P&L real", help="Consulta el historial de movimientos (~30 seg)"):
            with st.spinner("Calculando precio promedio desde historial... puede tardar ~30 seg"):
                client = PPIClient()
                st.session_state.cartera = client.enriquecer_con_pnl(st.session_state.cartera)
                st.session_state.pnl_cargado = True
                st.rerun()
    elif st.session_state.pnl_cargado:
        st.caption("✅ Precio promedio y P&L cargados desde historial de movimientos PPI")

    st.divider()

    # Tabla de posiciones
    filas = []
    for ticker, pos in cartera.items():
        precio_actual = pos.get("precio_actual_ars", 0) or 0
        precio_prom = pos.get("precio_promedio_ars")
        pnl_pct = pos.get("pnl_pct")
        pnl_usd = pos.get("pnl_usd")
        filas.append({
            "Ticker": ticker,
            "Nombre": pos.get("nombre", ticker),
            "Cant.": pos.get("cantidad", 0),
            "Precio actual ($)": f"{precio_actual:,.0f}",
            "Precio prom. ($)": f"{precio_prom:,.0f}" if precio_prom else "—",
            "Valor ($)": f"{pos.get('valor_total_ars', 0):,.0f}",
            "P&L %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
            "P&L USD": f"${pnl_usd:+,.0f}" if pnl_usd is not None else "—",
        })

    df = pd.DataFrame(filas)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Gráfico torta
    st.subheader("Composición")
    valores = {t: p.get("valor_total_ars", 0) or 0 for t, p in cartera.items()}
    fig = go.Figure(go.Pie(
        labels=list(valores.keys()),
        values=list(valores.values()),
        hole=0.4,
    ))
    fig.update_layout(height=350, margin=dict(t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Análisis rápido de toda la cartera
    if st.button("🤖 Analizar toda la cartera con IA", type="primary"):
        with st.spinner("Analizando... puede tardar 1-2 minutos"):
            from modules.advisor import analizar_cartera_completa
            resultados = analizar_cartera_completa(
                cartera=cartera,
                mensajes_broker=st.session_state.mensajes_broker or None,
            )
            for r in resultados:
                if "error" in r:
                    continue
                ticker_label = r.get("ticker", r.get("ticker_us", "?"))
                accion = r.get("accion", "")
                conviccion = r.get("conviccion", "")
                score = r.get("score_tecnico", 0)
                titulo = f"**{ticker_label}** — {accion} ({conviccion}) | score técnico: {score:+d}/10"
                with st.expander(titulo):
                    st.markdown(r["recomendacion"])


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN: ANALIZAR CEDEAR
# ══════════════════════════════════════════════════════════════════════════════
elif seccion == "Analizar CEDEAR":
    st.header("🔍 Analizar CEDEAR")

    col1, col2 = st.columns([2, 1])
    with col1:
        ticker = st.selectbox("Elegir CEDEAR", options=sorted(CEDEARS.keys()), index=0)
    with col2:
        precio_ars = st.number_input("Precio ARS actual (0 = estimar)", min_value=0, value=0, step=1000)

    if st.button("Analizar", type="primary"):
        with st.spinner(f"Analizando {ticker}..."):
            precio_input = precio_ars if precio_ars > 0 else None
            resultado = analizar_cedear(
                ticker_byma=ticker,
                precio_ars=precio_input,
                mensajes_broker=st.session_state.mensajes_broker or None,
                cartera_actual=st.session_state.cartera,
            )

        if "error" in resultado:
            st.error(resultado["error"])
        else:
            # Score técnico
            score = resultado.get("score_tecnico", 0)
            conclusion = resultado.get("conclusion_tecnica", "")
            color = "compra" if score >= 2 else ("venta" if score <= -2 else "neutro")

            col1, col2, col3 = st.columns(3)
            col1.metric("Score técnico", f"{score:+d}/10", delta=conclusion)
            col2.metric("P/E ratio", resultado["fundamentals"].get("pe_ratio", "N/A"))
            col3.metric(
                "Upside analistas",
                f"{resultado['fundamentals'].get('upside_pct', 'N/A')}%"
                if resultado['fundamentals'].get('upside_pct') else "N/A"
            )

            # Gráfico de precio histórico
            df_hist = get_precio_usd(resultado["ticker_us"], "6mo")
            if not df_hist.empty:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_hist.index,
                    open=df_hist["open"],
                    high=df_hist["high"],
                    low=df_hist["low"],
                    close=df_hist["close"],
                    name=resultado["ticker_us"],
                ))
                tec = resultado["tecnico"]
                if tec.get("ema20"):
                    ema20_series = df_hist["close"].ewm(span=20).mean()
                    fig.add_trace(go.Scatter(x=df_hist.index, y=ema20_series, name="EMA20", line=dict(color="orange", width=1)))
                if tec.get("ema50"):
                    ema50_series = df_hist["close"].ewm(span=50).mean()
                    fig.add_trace(go.Scatter(x=df_hist.index, y=ema50_series, name="EMA50", line=dict(color="blue", width=1)))
                fig.update_layout(title=f"{ticker} — Precio USD (6 meses)", height=400, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

            # Señales técnicas
            st.subheader("Señales técnicas")
            señales = resultado["tecnico"].get("señales", {})
            for indicador, (tipo, desc) in señales.items():
                icono = "🟢" if "COMPRA" in tipo else ("🔴" if "VENTA" in tipo else "🟡")
                st.markdown(f"{icono} **{indicador}**: {desc}")

            # CCL
            if resultado.get("ccl_analisis") and "error" not in resultado["ccl_analisis"]:
                ccl_d = resultado["ccl_analisis"]
                st.subheader("Análisis CCL")
                col1, col2, col3 = st.columns(3)
                col1.metric("CCL implícito", f"${ccl_d['ccl_implicito']:,.0f}")
                col2.metric("CCL real", f"${ccl_d['ccl_referencia']:,.0f}")
                col3.metric("Diferencia", f"{ccl_d['diferencia_pct']:+.1f}%", delta=ccl_d["señal_arbitraje"])

            # Recomendación Claude
            st.subheader("🤖 Recomendación IA")
            st.markdown(resultado["recomendacion"])


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN: OPORTUNIDADES
# ══════════════════════════════════════════════════════════════════════════════
elif seccion == "Oportunidades":
    st.header("💡 Oportunidades del mercado")

    tickers_a_analizar = st.multiselect(
        "CEDEARs a escanear",
        options=sorted(CEDEARS.keys()),
        default=CEDEARS_TOP_LIQUIDOS,
    )

    if st.button("🔍 Escanear oportunidades", type="primary"):
        resultados = []
        barra = st.progress(0, "Analizando...")

        for i, ticker in enumerate(tickers_a_analizar):
            barra.progress((i + 1) / len(tickers_a_analizar), f"Analizando {ticker}...")
            tec = analizar_tecnico(CEDEARS[ticker]["us"])
            resultados.append({
                "Ticker": ticker,
                "Nombre": CEDEARS[ticker]["nombre"],
                "Sector": CEDEARS[ticker]["sector"],
                "Score técnico": tec.get("score_tecnico", 0),
                "Señal": tec.get("conclusion", "N/A"),
                "RSI": tec.get("rsi"),
                "EMA20>EMA50": "✅" if (tec.get("ema20") and tec.get("ema50") and tec["ema20"] > tec["ema50"]) else "❌",
            })

        barra.empty()

        df_ops = pd.DataFrame(resultados).sort_values("Score técnico", ascending=False)
        st.dataframe(df_ops, use_container_width=True, hide_index=True)

        mejores = df_ops[df_ops["Score técnico"] >= 3]
        if not mejores.empty:
            st.success(f"**{len(mejores)} oportunidades de compra** encontradas: {', '.join(mejores['Ticker'].tolist())}")

        peores = df_ops[df_ops["Score técnico"] <= -3]
        if not peores.empty:
            st.warning(f"**{len(peores)} señales de venta**: {', '.join(peores['Ticker'].tolist())}")


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN: CHAT CON ASESOR
# ══════════════════════════════════════════════════════════════════════════════
elif seccion == "Chat con Asesor":
    st.header("💬 Chat con tu Asesor IA")
    st.caption("Preguntá cualquier cosa sobre CEDEARs, tu cartera, el mercado argentino...")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pregunta = st.chat_input("¿Qué querés analizar?")
    if pregunta:
        st.session_state.chat_history.append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)

        with st.chat_message("assistant"):
            with st.spinner("Analizando..."):
                respuesta = chat_libre(pregunta, contexto_cartera=st.session_state.cartera)
            st.markdown(respuesta)
            st.session_state.chat_history.append({"role": "assistant", "content": respuesta})


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN: MENSAJES BROKER
# ══════════════════════════════════════════════════════════════════════════════
elif seccion == "Mensajes Broker":
    st.header("📱 Mensajes del Broker PPI")

    tab1, tab2 = st.tabs(["Importar chat WhatsApp", "Ingresar mensaje manual"])

    with tab1:
        st.info(
            "**Cómo exportar:** Abrí el chat con PPI en WhatsApp → ⋮ → "
            "Exportar chat → Sin archivos → guardá el .txt en la carpeta `exports/`"
        )
        archivo = st.file_uploader("Subir archivo .txt de WhatsApp", type=["txt"])
        if archivo:
            ruta_temp = f"/tmp/whatsapp_ppi.txt"
            with open(ruta_temp, "wb") as f:
                f.write(archivo.read())
            mensajes = parsear_chat_whatsapp(ruta_temp)
            st.session_state.mensajes_broker = mensajes
            st.success(f"✅ {len(mensajes)} mensajes relevantes importados")

            if mensajes:
                df_msgs = pd.DataFrame([
                    {
                        "Fecha": m["fecha"].strftime("%d/%m %H:%M") if m["fecha"] else "?",
                        "Mensaje": m["texto"][:200],
                    }
                    for m in mensajes[-20:]
                ])
                st.dataframe(df_msgs, use_container_width=True, hide_index=True)

    with tab2:
        texto_msg = st.text_area("Pegá el mensaje de PPI acá", height=120)
        if st.button("Agregar mensaje"):
            if texto_msg.strip():
                msg = ingresar_mensaje_manual(texto_msg)
                st.session_state.mensajes_broker.append(msg)
                st.success("✅ Mensaje agregado. Se usará en los próximos análisis.")

    if st.session_state.mensajes_broker:
        st.metric("Mensajes cargados", len(st.session_state.mensajes_broker))
