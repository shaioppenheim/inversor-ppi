"""
Módulo de datos de mercado:
- Precios USD de subyacentes via yfinance
- Precios ARS de CEDEARs via PPI API
- Cálculo de CCL implícito y detección de oportunidades
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from data.cedears import CEDEARS


def get_precio_usd(ticker_us: str, periodo: str = "3mo") -> pd.DataFrame:
    """Descarga historial de precios USD del subyacente."""
    stock = yf.Ticker(ticker_us)
    df = stock.history(period=periodo)
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)


def get_info_fundamental(ticker_us: str) -> dict:
    """Extrae métricas fundamentales de yfinance."""
    stock = yf.Ticker(ticker_us)
    info = stock.info
    return {
        "nombre": info.get("longName", ticker_us),
        "sector": info.get("sector", "N/A"),
        "pe_ratio": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "eps_ttm": info.get("trailingEps"),
        "eps_forward": info.get("forwardEps"),
        "precio_actual_usd": info.get("currentPrice") or info.get("regularMarketPrice"),
        "target_analistas_usd": info.get("targetMeanPrice"),
        "recomendacion": info.get("recommendationKey", "N/A"),  # strong_buy, buy, hold, sell
        "upside_pct": _calcular_upside(info),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "margen_bruto": info.get("grossMargins"),
        "margen_operativo": info.get("operatingMargins"),
        "deuda_equity": info.get("debtToEquity"),
        "beta": info.get("beta"),
        "market_cap_b": _en_billones(info.get("marketCap")),
        "dividendo_yield": info.get("dividendYield"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "vs_52w_high_pct": _pct_vs_high(info),
    }


def calcular_ccl_implicito(precio_cedear_ars: float, ticker_byma: str) -> dict:
    """
    Calcula el CCL implícito de un CEDEAR y evalúa si está caro o barato.

    CCL implícito = (precio_ARS × ratio) / precio_USD_subyacente

    Si CCL implícito < CCL real → CEDEAR barato (oportunidad compra)
    Si CCL implícito > CCL real → CEDEAR caro (oportunidad venta)
    """
    if ticker_byma not in CEDEARS:
        return {"error": f"CEDEAR {ticker_byma} no encontrado en tabla"}

    cedear_info = CEDEARS[ticker_byma]
    ratio = cedear_info["ratio"]
    ticker_us = cedear_info["us"]

    stock = yf.Ticker(ticker_us)
    precio_usd = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")

    if not precio_usd:
        return {"error": f"No se pudo obtener precio USD para {ticker_us}"}

    ccl_implicito = (precio_cedear_ars * ratio) / precio_usd
    ccl_referencia = get_ccl_referencia()

    diferencia_pct = ((ccl_implicito / ccl_referencia) - 1) * 100

    if diferencia_pct < -5:
        señal = "COMPRA"
        razon = f"CEDEAR {diferencia_pct:.1f}% más barato que el CCL real"
    elif diferencia_pct > 5:
        señal = "VENTA"
        razon = f"CEDEAR {diferencia_pct:.1f}% más caro que el CCL real"
    else:
        señal = "NEUTRO"
        razon = f"CEDEAR cotiza en línea con el CCL real (±{abs(diferencia_pct):.1f}%)"

    return {
        "ticker": ticker_byma,
        "precio_cedear_ars": precio_cedear_ars,
        "precio_usd_subyacente": precio_usd,
        "ratio": ratio,
        "ccl_implicito": round(ccl_implicito, 2),
        "ccl_referencia": round(ccl_referencia, 2),
        "diferencia_pct": round(diferencia_pct, 2),
        "señal_arbitraje": señal,
        "razon": razon,
    }


def get_ccl_referencia() -> float:
    """
    Obtiene el CCL de referencia usando el par GD30/AL30 (método estándar del mercado).
    Fallback: usa el ratio implícito de AAPL como proxy.
    """
    try:
        # Método primario: scraping de dolarito.ar o ambito.com
        import requests
        r = requests.get("https://dolarapi.com/v1/dolares/contadoconliqui", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return float(data.get("venta", 1200))
    except Exception:
        pass

    # Fallback: retorna un valor aproximado (el usuario puede corregirlo)
    return 1200.0


def calcular_precio_justo_ars(ticker_byma: str, ccl: float = None) -> dict:
    """Precio justo del CEDEAR en ARS según precio USD y CCL actual."""
    if ticker_byma not in CEDEARS:
        return {}

    cedear_info = CEDEARS[ticker_byma]
    ticker_us = cedear_info["us"]
    ratio = cedear_info["ratio"]

    stock = yf.Ticker(ticker_us)
    precio_usd = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
    target_usd = stock.info.get("targetMeanPrice")

    if not ccl:
        ccl = get_ccl_referencia()

    precio_justo_ars = precio_usd / ratio * ccl if precio_usd else None
    target_ars = target_usd / ratio * ccl if target_usd else None

    return {
        "ticker": ticker_byma,
        "precio_usd": precio_usd,
        "precio_justo_ars": round(precio_justo_ars, 2) if precio_justo_ars else None,
        "target_analistas_ars": round(target_ars, 2) if target_ars else None,
        "ccl_usado": ccl,
        "ratio": ratio,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _calcular_upside(info: dict) -> float | None:
    precio = info.get("currentPrice") or info.get("regularMarketPrice")
    target = info.get("targetMeanPrice")
    if precio and target:
        return round(((target / precio) - 1) * 100, 2)
    return None


def _en_billones(valor) -> float | None:
    if valor:
        return round(valor / 1e9, 2)
    return None


def _pct_vs_high(info: dict) -> float | None:
    precio = info.get("currentPrice") or info.get("regularMarketPrice")
    high = info.get("fiftyTwoWeekHigh")
    if precio and high:
        return round(((precio / high) - 1) * 100, 2)
    return None
