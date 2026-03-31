"""
Motor de análisis sin dependencia de IA externa.
Genera recomendaciones basadas en reglas combinando:
- Score técnico (RSI, MACD, medias, Bollinger)
- Análisis fundamental (P/E, upside, earnings growth)
- CCL implícito vs CCL real (arbitraje cambiario)
- Mensajes del broker
"""

import json
from datetime import datetime, timedelta
from modules.market_data import get_info_fundamental, calcular_ccl_implicito, calcular_precio_justo_ars, get_ccl_referencia
from modules.technical import analizar_tecnico, resumen_tecnico_texto
from modules.whatsapp_parser import formatear_para_claude


def analizar_cedear(
    ticker_byma: str,
    precio_ars: float = None,
    mensajes_broker: list = None,
    cartera_actual: dict = None,
) -> dict:
    from data.cedears import CEDEARS
    if ticker_byma not in CEDEARS:
        return {"error": f"CEDEAR {ticker_byma} no está en la tabla"}

    ticker_us = CEDEARS[ticker_byma]["us"]

    print(f"  📊 Fundamentals {ticker_us}...")
    fundamentals = get_info_fundamental(ticker_us)

    print(f"  📈 Análisis técnico...")
    tecnico = analizar_tecnico(ticker_us, periodo="6mo")

    precio_justo = calcular_precio_justo_ars(ticker_byma)

    ccl_analisis = None
    if precio_ars:
        ccl_analisis = calcular_ccl_implicito(precio_ars, ticker_byma)

    # Posición actual
    posicion = None
    if cartera_actual and ticker_byma in cartera_actual:
        pos = cartera_actual[ticker_byma]
        pnl = None
        if precio_ars and pos.get("precio_promedio_ars"):
            pnl = ((precio_ars / pos["precio_promedio_ars"]) - 1) * 100
        posicion = {**pos, "pnl_actual_pct": round(pnl, 1) if pnl else None}

    recomendacion = generar_recomendacion(
        ticker=ticker_byma,
        tecnico=tecnico,
        fundamentals=fundamentals,
        ccl_analisis=ccl_analisis,
        precio_justo=precio_justo,
        precio_ars=precio_ars,
        mensajes_broker=mensajes_broker,
        posicion=posicion,
    )

    # Extraer accion/conviccion del texto generado para usarlos en el título
    accion_titulo, conviccion_titulo = _extraer_accion_conviccion(recomendacion)

    return {
        "ticker": ticker_byma,
        "ticker_us": ticker_us,
        "precio_ars": precio_ars,
        "fundamentals": fundamentals,
        "tecnico": tecnico,
        "ccl_analisis": ccl_analisis,
        "precio_justo": precio_justo,
        "recomendacion": recomendacion,
        "score_tecnico": tecnico.get("score_tecnico"),
        "conclusion_tecnica": tecnico.get("conclusion"),
        "accion": accion_titulo,
        "conviccion": conviccion_titulo,
    }


def generar_recomendacion(
    ticker, tecnico, fundamentals, ccl_analisis,
    precio_justo, precio_ars, mensajes_broker, posicion
) -> str:
    """
    Genera recomendación basada en reglas sin necesidad de IA externa.
    Combina score técnico + fundamentals + CCL en un score total.
    """
    score_tec = tecnico.get("score_tecnico", 0)
    upside = fundamentals.get("upside_pct")
    pe = fundamentals.get("pe_ratio")
    pe_forward = fundamentals.get("pe_forward")
    earnings_growth = fundamentals.get("earnings_growth")
    recomendacion_analistas = fundamentals.get("recomendacion", "")
    precio_usd = fundamentals.get("precio_actual_usd")
    target_usd = fundamentals.get("target_analistas_usd")
    vs_52w_high = fundamentals.get("vs_52w_high_pct")

    # ── Score fundamental (−5 a +5) ──────────────────────────────────────────
    score_fund = 0
    notas_fund = []

    if upside is not None:
        if upside > 20:
            score_fund += 2
            notas_fund.append(f"Upside {upside:.1f}% según consenso de analistas")
        elif upside > 10:
            score_fund += 1
            notas_fund.append(f"Upside moderado {upside:.1f}% según analistas")
        elif upside < -10:
            score_fund -= 2
            notas_fund.append(f"Downside {upside:.1f}% — precio por encima del target")
        elif upside < 0:
            score_fund -= 1

    if recomendacion_analistas in ("strong_buy", "buy"):
        score_fund += 1
        notas_fund.append(f"Consenso analistas: {recomendacion_analistas.replace('_', ' ').upper()}")
    elif recomendacion_analistas in ("sell", "strong_sell", "underperform"):
        score_fund -= 1
        notas_fund.append(f"Consenso analistas: {recomendacion_analistas.replace('_', ' ').upper()}")

    if earnings_growth is not None:
        if earnings_growth > 0.15:
            score_fund += 1
            notas_fund.append(f"Crecimiento de ganancias sólido: {earnings_growth*100:.1f}% anual")
        elif earnings_growth < -0.1:
            score_fund -= 1
            notas_fund.append(f"Caída en ganancias: {earnings_growth*100:.1f}%")

    if vs_52w_high is not None:
        if vs_52w_high < -30:
            score_fund += 1
            notas_fund.append(f"Precio {abs(vs_52w_high):.0f}% abajo del máximo de 52 semanas — zona de valor")
        elif vs_52w_high > -5:
            score_fund -= 1
            notas_fund.append(f"Precio cerca del máximo de 52 semanas ({vs_52w_high:.1f}%)")

    score_fund = max(-5, min(5, score_fund))

    # ── CCL implícito — solo informativo, no afecta el score ─────────────────
    # El usuario mide retornos en USD → el CCL no cambia si la acción sube o baja en dólares
    score_ccl = 0
    nota_ccl = ""
    if ccl_analisis and "error" not in ccl_analisis:
        diff = ccl_analisis.get("diferencia_pct", 0)
        if abs(diff) > 200:
            nota_ccl = ""  # dato incorrecto, no mostrar
        elif diff < -10:
            nota_ccl = f"CCL implícito {abs(diff):.1f}% bajo el CCL real (ref. solo — no afecta retorno en USD)"
        elif diff > 10:
            nota_ccl = f"CCL implícito {diff:.1f}% sobre el CCL real (ref. solo — no afecta retorno en USD)"
        else:
            nota_ccl = f"CCL implícito alineado con el real (diferencia: {diff:+.1f}%)"

    # ── Score total: solo técnico + fundamental (medición en USD) ─────────────
    score_total = score_tec + score_fund

    # ── Acción recomendada (score /10: técnico + fundamental) ────────────────
    if score_total >= 5:
        accion = "COMPRAR"
        conviccion = "ALTA"
        emoji = "🟢"
    elif score_total >= 2:
        accion = "COMPRAR"
        conviccion = "MODERADA"
        emoji = "🟢"
    elif score_total >= 0:
        accion = "MANTENER / ESPERAR ENTRADA"
        conviccion = "BAJA"
        emoji = "🟡"
    elif score_total >= -3:
        accion = "MANTENER"
        conviccion = "NEUTRAL"
        emoji = "🟡"
    elif score_total >= -5:
        accion = "REDUCIR POSICIÓN"
        conviccion = "MODERADA"
        emoji = "🔴"
    else:
        accion = "VENDER"
        conviccion = "ALTA"
        emoji = "🔴"

    # ── Precio objetivo ───────────────────────────────────────────────────────
    ccl_ref = get_ccl_referencia()
    lineas_precio = []
    if precio_justo.get("precio_justo_ars"):
        pj = precio_justo["precio_justo_ars"]
        lineas_precio.append(f"  • Precio justo actual (CCL ${ccl_ref:,.0f}): **${pj:,.0f} ARS**")
    if precio_justo.get("target_analistas_ars"):
        ta = precio_justo["target_analistas_ars"]
        lineas_precio.append(f"  • Target analistas (CCL actual): **${ta:,.0f} ARS**")
        # Proyección con CCL +20% a 6 meses
        ta_6m = ta * 1.20
        lineas_precio.append(f"  • Target a 6 meses (CCL +20%): **${ta_6m:,.0f} ARS**")

    # Stop loss sugerido (soporte técnico o -8% desde entrada)
    soporte = tecnico.get("soporte_20d")
    if precio_ars and soporte:
        stop = min(soporte, precio_ars * 0.92)
        lineas_precio.append(f"  • Stop loss sugerido: **${stop:,.0f} ARS** (soporte técnico o -8%)")
    elif precio_ars:
        lineas_precio.append(f"  • Stop loss sugerido: **${precio_ars * 0.92:,.0f} ARS** (-8% desde entrada)")

    # ── Factores clave ────────────────────────────────────────────────────────
    factores = []
    señales_tec = tecnico.get("señales", {})
    for ind, (tipo, desc) in list(señales_tec.items())[:3]:
        icono = "↑" if "COMPRA" in tipo else ("↓" if "VENTA" in tipo else "→")
        factores.append(f"  {icono} **{ind}**: {desc}")
    for nota in notas_fund[:2]:
        factores.append(f"  → {nota}")
    if nota_ccl:
        factores.append(f"  💱 **CCL**: {nota_ccl}")

    # Mensajes broker
    broker_resumen = ""
    if mensajes_broker:
        broker_resumen = f"\n**Broker PPI:** {len(mensajes_broker)} mensajes recientes cargados sobre este ticker."

    # P&L actual
    pnl_texto = ""
    if posicion and posicion.get("pnl_actual_pct") is not None:
        pnl = posicion["pnl_actual_pct"]
        pnl_texto = f"\n**Tu posición actual:** {posicion.get('cantidad')} unidades | P&L: **{pnl:+.1f}%**"

    # ── Riesgo ────────────────────────────────────────────────────────────────
    beta = fundamentals.get("beta")
    if beta is None:
        riesgo = "MEDIO"
    elif beta > 1.5:
        riesgo = "ALTO (beta {:.2f})".format(beta)
    elif beta < 0.8:
        riesgo = "BAJO (beta {:.2f})".format(beta)
    else:
        riesgo = "MEDIO (beta {:.2f})".format(beta)

    # ── Alternativa de compra si la señal es negativa ─────────────────────────
    alternativa = ""
    if "VENDER" in accion or "REDUCIR" in accion:
        alternativa = _sugerir_alternativa(ticker, score_tec, score_fund)

    # ── Proyección de revisión (siempre que no sea COMPRAR con alta convicción)
    revision = ""
    if not (accion == "COMPRAR" and conviccion == "ALTA"):
        revision = proyectar_revision(ticker, tecnico, fundamentals, ccl_analisis, precio_ars, accion, conviccion)

    # ── Por qué esta recomendación ────────────────────────────────────────────
    explicacion = _explicar_scores(score_tec, score_fund, score_ccl, score_total,
                                   tecnico, fundamentals, nota_ccl)

    # ── Armar texto final ─────────────────────────────────────────────────────
    # Precios en USD (métrica principal) + ARS como referencia
    from data.cedears import CEDEARS as _C
    ccl_ref = get_ccl_referencia()
    ratio = _C.get(ticker, {}).get("ratio", 1)
    lineas_precio = []

    precio_actual_usd = fundamentals.get("precio_actual_usd")
    target_usd = fundamentals.get("target_analistas_usd")
    upside_usd = fundamentals.get("upside_pct")

    if precio_actual_usd:
        lineas_precio.append(f"- Precio actual: **${precio_actual_usd:.2f} USD**")
    if target_usd and upside_usd is not None:
        lineas_precio.append(f"- Target analistas: **${target_usd:.2f} USD** (upside: {upside_usd:+.1f}%)")
    if precio_justo.get("precio_justo_ars") and ccl_ref:
        pj_usd = precio_justo["precio_justo_ars"] / ccl_ref
        lineas_precio.append(f"- Precio justo estimado: **${pj_usd:.2f} USD**")

    # Stop loss en USD
    soporte_usd = tecnico.get("soporte_20d")
    if precio_actual_usd and soporte_usd:
        stop_usd = min(soporte_usd, precio_actual_usd * 0.92)
        lineas_precio.append(f"- Stop loss sugerido: **${stop_usd:.2f} USD** (-8% o soporte técnico)")
    elif precio_actual_usd:
        lineas_precio.append(f"- Stop loss sugerido: **${precio_actual_usd * 0.92:.2f} USD** (-8%)")

    pnl_texto = ""
    if posicion and posicion.get("pnl_actual_pct") is not None:
        pnl_pct = posicion["pnl_actual_pct"]
        pnl_texto = f"**Tu posición:** {posicion.get('cantidad')} unidades | P&L en USD: **{pnl_pct:+.1f}%**"

    broker_resumen = f"\n**Broker PPI:** {len(mensajes_broker)} mensajes recientes cargados." if mensajes_broker else ""

    partes = [
        f"## {emoji} {accion} — Convicción: {conviccion}",
        "",
        f"**Score total: {score_total:+d}/10** = técnico {score_tec:+d} + fundamental {score_fund:+d}",
        pnl_texto,
        "",
        "### ¿Por qué esta recomendación?",
        explicacion,
        "",
        "### Precios objetivo",
        *lineas_precio,
        "",
        f"**Riesgo:** {riesgo}",
        broker_resumen,
        revision,
        alternativa,
    ]

    return "\n".join(x for x in partes if x is not None)


def analizar_cartera_completa(cartera: dict, mensajes_broker: list = None) -> list:
    resultados = []
    for ticker, pos in cartera.items():
        print(f"\n🔍 Analizando {ticker}...")
        resultado = analizar_cedear(
            ticker_byma=ticker,
            precio_ars=pos.get("precio_actual_ars"),
            mensajes_broker=mensajes_broker,
            cartera_actual=cartera,
        )
        resultados.append(resultado)
    resultados.sort(key=lambda r: r.get("score_tecnico") or 0, reverse=True)
    return resultados


def chat_libre(pregunta: str, contexto_cartera: dict = None) -> str:
    """Sin IA externa: responde con análisis estructurado de la cartera."""
    ccl = get_ccl_referencia()
    lineas = [
        "**Análisis basado en datos de mercado en tiempo real**",
        f"CCL de referencia: ${ccl:,.0f}",
        "",
    ]

    if contexto_cartera:
        lineas.append("**Cartera actual:**")
        for ticker, pos in contexto_cartera.items():
            valor = pos.get("valor_total_ars", 0) or 0
            pnl = pos.get("pnl_pct", 0) or 0
            lineas.append(f"  • {ticker}: ${valor:,.0f} ARS | P&L: {pnl:+.1f}%")
        lineas.append("")

    lineas += [
        f"**Tu pregunta:** {pregunta}",
        "",
        "Para análisis detallado de un CEDEAR específico, usá la sección **'Analizar CEDEAR'**.",
        "Para ver oportunidades del mercado, usá **'Oportunidades'**.",
    ]
    return "\n".join(lineas)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _explicar_scores(score_tec, score_fund, score_ccl, score_total, tecnico, fundamentals, nota_ccl) -> str:
    """Explica en lenguaje claro qué aportó cada componente al score."""
    lineas = []

    # Score técnico
    señales = tecnico.get("señales", {})
    positivas = [d for _, (t, d) in señales.items() if "COMPRA" in t]
    negativas = [d for _, (t, d) in señales.items() if "VENTA" in t]

    if score_tec >= 3:
        lineas.append(f"**Técnico {score_tec:+d}/10** ✅ — Señales alcistas dominan:")
    elif score_tec <= -3:
        lineas.append(f"**Técnico {score_tec:+d}/10** ❌ — Señales bajistas dominan:")
    else:
        lineas.append(f"**Técnico {score_tec:+d}/10** ⚠️ — Señales mixtas:")
    for s in positivas[:2]:
        lineas.append(f"  ✅ {s}")
    for s in negativas[:2]:
        lineas.append(f"  ❌ {s}")

    # Score fundamental
    upside = fundamentals.get("upside_pct")
    pe = fundamentals.get("pe_ratio")
    vs_high = fundamentals.get("vs_52w_high_pct")
    rec = fundamentals.get("recomendacion", "")
    eg = fundamentals.get("earnings_growth")

    lineas.append(f"\n**Fundamental {score_fund:+d}/5**:")
    if upside is not None:
        emoji_up = "✅" if upside > 10 else ("❌" if upside < 0 else "⚠️")
        lineas.append(f"  {emoji_up} Upside según analistas: {upside:+.1f}%")
    if rec:
        lineas.append(f"  {'✅' if 'buy' in rec else '⚠️'} Consenso Wall Street: {rec.replace('_',' ').upper()}")
    if vs_high is not None:
        emoji_h = "✅" if vs_high < -20 else ("⚠️" if vs_high < -5 else "❌")
        lineas.append(f"  {emoji_h} Vs máximo 52 semanas: {vs_high:.1f}% ({'lejos del techo' if vs_high < -20 else 'cerca del techo'})")
    if eg is not None:
        emoji_eg = "✅" if eg > 0.1 else ("❌" if eg < -0.1 else "⚠️")
        lineas.append(f"  {emoji_eg} Crecimiento de ganancias: {eg*100:.1f}% anual")

    # CCL — solo referencia, no afecta score
    if nota_ccl:
        lineas.append(f"\n**CCL implícito** (referencia, no afecta score — medición en USD):")
        lineas.append(f"  ℹ️ {nota_ccl}")

    return "\n".join(lineas)


def proyectar_revision(ticker, tecnico, fundamentals, ccl_analisis, precio_ars, accion="", conviccion="") -> str:
    """
    Estima cuándo volver a revisar el CEDEAR.
    El mensaje se adapta según la acción actual:
    - Si ya es COMPRAR: explica qué frena la convicción ALTA y cuándo mejoraría
    - Si es MANTENER/ESPERAR: indica qué falta para señal de COMPRAR
    - Si es REDUCIR/VENDER: indica qué falta para reconsiderar
    """
    precio    = tecnico.get("precio_actual")
    ema20     = tecnico.get("ema20")
    ema50     = tecnico.get("ema50")
    rsi       = tecnico.get("rsi")
    señales   = tecnico.get("señales", {})

    fricciones = []   # factores que limitan la convicción o la señal
    dias_estimados = 0

    ya_es_compra = "COMPRAR" in accion

    # ── Precio bajo EMA20 (señal bajista a corto plazo) ───────────────────────
    if precio and ema20 and precio < ema20:
        distancia_pct = ((ema20 - precio) / precio) * 100
        macd_alcista = señales.get("MACD", ("",))[0] in ("COMPRA", "COMPRA_DÉBIL")
        dias_ema = int(distancia_pct * (3 if macd_alcista else 6))
        dias_estimados = max(dias_estimados, dias_ema)
        fricciones.append(
            f"Precio {distancia_pct:.1f}% debajo de EMA20 (${ema20:,.2f}) — confirmaría tendencia si lo supera"
        )

    # ── RSI bajo 50 (momentum no alcista) ─────────────────────────────────────
    if rsi and rsi < 50:
        dias_rsi = int((50 - rsi) * 1.5)
        dias_estimados = max(dias_estimados, dias_rsi)
        fricciones.append(
            f"RSI en {rsi:.1f} — por debajo de 50 el momentum es neutral/bajista"
        )

    # CCL no se considera como fricción — el retorno se mide en USD

    # ── Tendencia bajista de largo plazo (EMA20 < EMA50) ──────────────────────
    tendencia = señales.get("TENDENCIA", ("",))[0]
    if "VENTA" in tendencia and ema20 and ema50:
        gap_pct = abs((ema20 - ema50) / ema50) * 100
        dias_tendencia = int(gap_pct * 5)
        dias_estimados = max(dias_estimados, dias_tendencia)
        fricciones.append(
            f"Tendencia bajista: EMA20 (${ema20:,.2f}) < EMA50 (${ema50:,.2f})"
        )

    # ── Resultado sin fricciones ───────────────────────────────────────────────
    if not fricciones:
        if ya_es_compra:
            return "\n### 📅 Revisión\n✅ Todas las condiciones alineadas — convicción máxima, revisá en 2 semanas."
        return "\n### 📅 Revisión\n✅ Ya cumple condiciones de entrada — revisá esta semana."

    dias_estimados = max(7, min(90, dias_estimados))
    fecha_revision = datetime.now() + timedelta(days=dias_estimados)
    semanas = dias_estimados // 7

    lineas = ["\n---", "### 📅 ¿Cuándo volver a revisar?",
              f"**Próxima revisión sugerida: {fecha_revision.strftime('%d/%m/%Y')} (~{semanas} {'semana' if semanas == 1 else 'semanas'})**", ""]

    if ya_es_compra:
        # La señal ya es COMPRAR — explicamos qué frena la convicción ALTA
        lineas.append(f"**La señal es COMPRAR ahora.** La convicción es {conviccion} (no ALTA) por estos factores:")
        for i, f in enumerate(fricciones, 1):
            lineas.append(f"  {i}. {f}")
        lineas += [
            "",
            "**¿Qué significan para vos?**",
            "  - Podés comprar hoy — el análisis técnico y fundamental lo justifican",
            "  - Los factores de arriba reducen el upside potencial en ARS pero no invalidan la entrada",
            "  - Si esperás que se resuelvan, el punto de entrada sería más favorable",
        ]
    elif "MANTENER" in accion or "ESPERAR" in accion:
        lineas.append("Condiciones que falta cumplir para señal de **COMPRAR**:")
        for i, f in enumerate(fricciones, 1):
            lineas.append(f"  {i}. {f}")
    else:
        lineas.append("Condiciones para reconsiderar la posición:")
        for i, f in enumerate(fricciones, 1):
            lineas.append(f"  {i}. {f}")

    lineas += [
        "",
        "💡 **Revisá antes si:**",
        "  - El precio cae más del 10% (mejor punto de entrada)",
        "  - El broker PPI envía señal de compra específica para este ticker",
        f"  - Se anuncian earnings de {fundamentals.get('nombre', ticker)} mejor al esperado",
    ]

    return "\n".join(lineas)


def _sugerir_alternativa(ticker_vendido: str, score_tec: int, score_fund: int) -> str:
    """Cuando se recomienda vender X, sugiere CEDEARs alternativos para reubicar el capital."""
    from data.cedears import CEDEARS
    from modules.technical import analizar_tecnico

    candidatos = {
        "AAPL": ["MSFT", "GOOGL", "NVDA"],
        "MSFT": ["GOOGL", "AAPL", "META"],
        "NVDA": ["AMD", "MSFT", "GOOGL"],
        "META": ["GOOGL", "NFLX", "AMZN"],
        "TSLA": ["NVDA", "AAPL", "AMZN"],
        "MELI": ["AMZN", "GOOGL", "META"],
    }
    alternativas_ticker = candidatos.get(ticker_vendido, ["SPY", "QQQ", "MSFT"])

    lineas = ["\n---", "### ♻️ ¿Dónde reubicar el capital?"]
    lineas.append(f"Si reducís o vendés {ticker_vendido}, estos CEDEARs tienen mejor momento técnico ahora:\n")

    for alt in alternativas_ticker[:3]:
        if alt not in CEDEARS:
            continue
        tec = analizar_tecnico(CEDEARS[alt]["us"], "3mo")
        score = tec.get("score_tecnico", 0)
        conclusion = tec.get("conclusion", "")
        emoji = "🟢" if score >= 2 else ("🟡" if score >= 0 else "🔴")
        lineas.append(f"  {emoji} **{alt}** ({CEDEARS[alt]['nombre']}) — Score técnico: {score:+d} | {conclusion}")

    return "\n".join(lineas)


def _extraer_accion_conviccion(recomendacion: str) -> tuple:
    """Extrae accion y conviccion de la primera línea del texto generado."""
    for linea in recomendacion.splitlines():
        if "Convicción:" in linea:
            # Formato: "## 🟢 COMPRAR — Convicción: MODERADA"
            partes = linea.split("—")
            accion = partes[0].replace("#", "").strip()
            for emoji in ["🟢", "🟡", "🔴"]:
                accion = accion.replace(emoji, "").strip()
            conviccion = partes[1].replace("Convicción:", "").strip() if len(partes) > 1 else ""
            return accion, conviccion
    return "", ""


def _resumen_ejecutivo(ticker, accion, score, upside, nota_ccl) -> str:
    if "COMPRAR" in accion and upside and upside > 15:
        return f"{ticker} combina momentum técnico favorable con upside de {upside:.0f}% según analistas."
    elif "COMPRAR" in accion and nota_ccl and "barato" in nota_ccl:
        return f"{ticker} está cambiariamente barato — oportunidad de entrada antes de ajuste del CCL."
    elif "VENDER" in accion:
        return f"{ticker} muestra señales de debilidad técnica y fundamental — considerar reducir exposición."
    elif "REDUCIR" in accion:
        return f"{ticker} en zona de precaución — evaluar toma parcial de ganancias."
    else:
        return f"{ticker} sin señal clara — esperar confirmación antes de tomar posición."
