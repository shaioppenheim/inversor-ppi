"""
Análisis técnico de CEDEARs usando la librería 'ta'.
Genera señales de compra/venta basadas en indicadores clásicos.
"""

import pandas as pd
import ta
from modules.market_data import get_precio_usd


def analizar_tecnico(ticker_us: str, periodo: str = "6mo") -> dict:
    """
    Calcula indicadores técnicos y genera señales para un ticker.

    Returns dict con:
    - indicadores actuales (RSI, MACD, Bollinger, medias)
    - señales (compra/venta/neutro por indicador)
    - score_tecnico: -10 a +10 (positivo = alcista)
    - conclusion: string legible
    """
    df = get_precio_usd(ticker_us, periodo)

    if df.empty or len(df) < 50:
        return {"error": f"Datos insuficientes para {ticker_us}"}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # ── Calcular indicadores ──────────────────────────────────────────────────
    df["rsi"] = ta.momentum.RSIIndicator(close, window=14).rsi()
    df["ema20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(close, window=200).ema_indicator()

    macd_obj = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
    df["macd"] = macd_obj.macd()
    df["macd_signal"] = macd_obj.macd_signal()
    df["macd_hist"] = macd_obj.macd_diff()

    bb_obj = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb_obj.bollinger_hband()
    df["bb_lower"] = bb_obj.bollinger_lband()
    df["bb_mid"] = bb_obj.bollinger_mavg()

    df["vol_ratio"] = volume / volume.rolling(20).mean()

    # ── Última fila y anterior ────────────────────────────────────────────────
    last = df.iloc[-1]
    prev = df.iloc[-2]

    precio    = last["close"]
    rsi       = last["rsi"]
    ema20     = last["ema20"]
    ema50     = last["ema50"]
    ema200    = last["ema200"]
    macd_val  = last["macd"]
    macd_sig  = last["macd_signal"]
    bb_upper  = last["bb_upper"]
    bb_lower  = last["bb_lower"]
    vol_ratio = last["vol_ratio"] if pd.notna(last["vol_ratio"]) else 1.0

    # ── Señales individuales ─────────────────────────────────────────────────
    señales = {}
    score = 0

    # RSI
    if pd.notna(rsi):
        if rsi < 30:
            señales["RSI"] = ("COMPRA", f"RSI={rsi:.1f} — sobreventa extrema")
            score += 2
        elif rsi < 40:
            señales["RSI"] = ("COMPRA_DÉBIL", f"RSI={rsi:.1f} — zona de interés")
            score += 1
        elif rsi > 70:
            señales["RSI"] = ("VENTA", f"RSI={rsi:.1f} — sobrecompra extrema")
            score -= 2
        elif rsi > 60:
            señales["RSI"] = ("VENTA_DÉBIL", f"RSI={rsi:.1f} — sobrecompra moderada")
            score -= 1
        else:
            señales["RSI"] = ("NEUTRO", f"RSI={rsi:.1f} — zona neutral")

    # Medias móviles (tendencia)
    if pd.notna(ema20) and pd.notna(ema50):
        prev_ema20 = prev["ema20"]
        prev_ema50 = prev["ema50"]
        if precio > ema20 > ema50:
            señales["TENDENCIA"] = ("COMPRA", "Precio > EMA20 > EMA50 — tendencia alcista")
            score += 2
        elif precio < ema20 < ema50:
            señales["TENDENCIA"] = ("VENTA", "Precio < EMA20 < EMA50 — tendencia bajista")
            score -= 2
        elif ema20 > ema50 and pd.notna(prev_ema20) and pd.notna(prev_ema50) and prev_ema20 <= prev_ema50:
            señales["TENDENCIA"] = ("COMPRA", "Cruce dorado EMA20/EMA50 — señal alcista fuerte")
            score += 3
        elif ema20 < ema50 and pd.notna(prev_ema20) and pd.notna(prev_ema50) and prev_ema20 >= prev_ema50:
            señales["TENDENCIA"] = ("VENTA", "Cruce de la muerte EMA20/EMA50 — señal bajista")
            score -= 3
        else:
            señales["TENDENCIA"] = ("NEUTRO", "Sin tendencia clara en medias móviles")

    # EMA200 (largo plazo)
    if pd.notna(ema200):
        if precio > ema200:
            señales["LARGO_PLAZO"] = ("COMPRA", "Precio sobre EMA200 — mercado alcista de largo plazo")
            score += 1
        else:
            señales["LARGO_PLAZO"] = ("VENTA", "Precio bajo EMA200 — mercado bajista de largo plazo")
            score -= 1

    # MACD
    if pd.notna(macd_val) and pd.notna(macd_sig):
        prev_macd = prev["macd"]
        prev_sig  = prev["macd_signal"]
        if macd_val > macd_sig and pd.notna(prev_macd) and pd.notna(prev_sig) and prev_macd <= prev_sig:
            señales["MACD"] = ("COMPRA", "Cruce alcista MACD — momentum positivo")
            score += 2
        elif macd_val < macd_sig and pd.notna(prev_macd) and pd.notna(prev_sig) and prev_macd >= prev_sig:
            señales["MACD"] = ("VENTA", "Cruce bajista MACD — momentum negativo")
            score -= 2
        elif macd_val > macd_sig:
            señales["MACD"] = ("COMPRA_DÉBIL", "MACD sobre señal — momentum alcista")
            score += 1
        else:
            señales["MACD"] = ("VENTA_DÉBIL", "MACD bajo señal — momentum bajista")
            score -= 1

    # Bollinger Bands
    if pd.notna(bb_upper) and pd.notna(bb_lower):
        if precio < bb_lower:
            señales["BOLLINGER"] = ("COMPRA", "Precio bajo banda inferior — posible rebote")
            score += 2
        elif precio > bb_upper:
            señales["BOLLINGER"] = ("VENTA", "Precio sobre banda superior — posible corrección")
            score -= 2
        else:
            pos_bb = (precio - bb_lower) / (bb_upper - bb_lower) * 100
            señales["BOLLINGER"] = ("NEUTRO", f"Precio en {pos_bb:.0f}% del canal Bollinger")

    # Volumen confirmador
    if vol_ratio > 1.5:
        if score > 0:
            señales["VOLUMEN"] = ("CONFIRMA_COMPRA", f"Volumen {vol_ratio:.1f}x la media — confirma movimiento alcista")
            score += 1
        elif score < 0:
            señales["VOLUMEN"] = ("CONFIRMA_VENTA", f"Volumen {vol_ratio:.1f}x la media — confirma movimiento bajista")
            score -= 1

    # ── Score y conclusión ────────────────────────────────────────────────────
    score = max(-10, min(10, score))

    if score >= 4:
        conclusion = "COMPRA FUERTE"
    elif score >= 2:
        conclusion = "COMPRA"
    elif score >= 0:
        conclusion = "MANTENER"
    elif score >= -2:
        conclusion = "PRECAUCIÓN"
    elif score >= -4:
        conclusion = "VENTA"
    else:
        conclusion = "VENTA FUERTE"

    # Soporte y resistencia últimas 4 semanas
    df_20d = df.tail(20)
    soporte     = round(df_20d["low"].min(), 2)
    resistencia = round(df_20d["high"].max(), 2)

    return {
        "ticker_us": ticker_us,
        "precio_actual": round(precio, 2),
        "rsi":       round(rsi, 1)     if pd.notna(rsi)     else None,
        "ema20":     round(ema20, 2)   if pd.notna(ema20)   else None,
        "ema50":     round(ema50, 2)   if pd.notna(ema50)   else None,
        "ema200":    round(ema200, 2)  if pd.notna(ema200)  else None,
        "macd":      round(macd_val, 4) if pd.notna(macd_val) else None,
        "macd_signal": round(macd_sig, 4) if pd.notna(macd_sig) else None,
        "bb_upper":  round(bb_upper, 2) if pd.notna(bb_upper) else None,
        "bb_lower":  round(bb_lower, 2) if pd.notna(bb_lower) else None,
        "soporte_20d":     soporte,
        "resistencia_20d": resistencia,
        "vol_ratio": round(vol_ratio, 2),
        "señales":   señales,
        "score_tecnico": score,
        "conclusion":    conclusion,
    }


def resumen_tecnico_texto(analisis: dict) -> str:
    """Genera texto legible para incluir en el prompt de Claude."""
    if "error" in analisis:
        return f"Error análisis técnico: {analisis['error']}"

    lineas = [
        f"ANÁLISIS TÉCNICO {analisis['ticker_us']} — Precio: ${analisis['precio_actual']}",
        f"Score técnico: {analisis['score_tecnico']}/10 → {analisis['conclusion']}",
        "",
        "Señales:",
    ]
    for indicador, (tipo, desc) in analisis["señales"].items():
        lineas.append(f"  • {indicador}: {tipo} — {desc}")

    lineas += [
        "",
        f"Soporte 20d: ${analisis['soporte_20d']} | Resistencia 20d: ${analisis['resistencia_20d']}",
        f"RSI: {analisis['rsi']} | EMA20: ${analisis['ema20']} | EMA50: ${analisis['ema50']}",
    ]
    return "\n".join(lineas)
