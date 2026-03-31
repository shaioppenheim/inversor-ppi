"""
Parser de mensajes de WhatsApp exportados desde el broker PPI.

Uso:
1. En WhatsApp: chat con PPI → ⋮ → Exportar chat → Sin archivos → guardar como .txt
2. Colocar el archivo en exports/whatsapp_ppi.txt
3. Este módulo parsea y extrae las recomendaciones

También soporta ingreso manual de mensajes.
"""

import re
from datetime import datetime
from pathlib import Path


# Patrones comunes en mensajes de brokers argentinos
PATRONES_TICKER = re.compile(
    r'\b(AAPL|MSFT|GOOGL|AMZN|NVDA|META|TSLA|BRKB|MELI|JPM|GS|XOM|CVX|'
    r'NFLX|AMD|INTC|CRM|PYPL|BAC|V|MA|MCD|KO|DIS|WMT|SPY|QQQ|SQ|ORCL)\b',
    re.IGNORECASE
)

PATRONES_ACCION = re.compile(
    r'\b(comprar?|vender?|mantener?|posicionarse|salir|ingresar|tomar ganancias|'
    r'stop loss|entrada|salida|objetivo)\b',
    re.IGNORECASE
)

PATRONES_PRECIO = re.compile(r'\$\s?[\d.,]+')


def parsear_chat_whatsapp(ruta_archivo: str) -> list[dict]:
    """
    Parsea un archivo .txt exportado de WhatsApp.
    Retorna lista de mensajes relevantes sobre inversiones.
    """
    path = Path(ruta_archivo)
    if not path.exists():
        return []

    contenido = path.read_text(encoding="utf-8")
    mensajes = _extraer_mensajes(contenido)
    relevantes = [m for m in mensajes if _es_relevante(m["texto"])]

    return relevantes


def _extraer_mensajes(texto: str) -> list[dict]:
    """Extrae mensajes individuales del formato WhatsApp."""
    # Formato: DD/MM/YYYY, HH:MM - Remitente: Mensaje
    patron = re.compile(
        r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2})(?::\d{2})?\s*[-–]\s*([^:]+):\s*(.*?)(?=\d{1,2}/\d{1,2}/\d{2,4}|$)',
        re.DOTALL
    )

    mensajes = []
    for match in patron.finditer(texto):
        fecha_str, hora_str, remitente, mensaje = match.groups()
        try:
            fecha = datetime.strptime(f"{fecha_str.strip()} {hora_str.strip()}", "%d/%m/%Y %H:%M")
        except ValueError:
            try:
                fecha = datetime.strptime(f"{fecha_str.strip()} {hora_str.strip()}", "%d/%m/%y %H:%M")
            except ValueError:
                fecha = None

        mensajes.append({
            "fecha": fecha,
            "remitente": remitente.strip(),
            "texto": mensaje.strip().replace("\n", " "),
        })

    return mensajes


def _es_relevante(texto: str) -> bool:
    """Filtra mensajes que mencionan tickers o acciones de inversión."""
    tiene_ticker = bool(PATRONES_TICKER.search(texto))
    tiene_accion = bool(PATRONES_ACCION.search(texto))
    tiene_precio = bool(PATRONES_PRECIO.search(texto))
    return tiene_ticker or (tiene_accion and tiene_precio)


def extraer_tickers_mencionados(mensajes: list[dict]) -> dict[str, list]:
    """Agrupa mensajes por ticker mencionado."""
    por_ticker = {}
    for msg in mensajes:
        tickers_en_msg = PATRONES_TICKER.findall(msg["texto"])
        for ticker in set(t.upper() for t in tickers_en_msg):
            if ticker not in por_ticker:
                por_ticker[ticker] = []
            por_ticker[ticker].append(msg)
    return por_ticker


def formatear_para_claude(mensajes: list[dict], ticker: str = None, ultimos_n: int = 10) -> str:
    """Formatea los últimos mensajes para incluir en el prompt de Claude."""
    if ticker:
        mensajes = [m for m in mensajes if ticker.upper() in PATRONES_TICKER.findall(m["texto"].upper())]

    mensajes = sorted(mensajes, key=lambda m: m["fecha"] or datetime.min, reverse=True)[:ultimos_n]
    mensajes = sorted(mensajes, key=lambda m: m["fecha"] or datetime.min)

    if not mensajes:
        return "Sin mensajes del broker para este ticker."

    lineas = [f"MENSAJES DEL BROKER PPI{' — ' + ticker if ticker else ''}:"]
    for msg in mensajes:
        fecha_str = msg["fecha"].strftime("%d/%m %H:%M") if msg["fecha"] else "?"
        lineas.append(f"  [{fecha_str}] {msg['texto']}")

    return "\n".join(lineas)


def ingresar_mensaje_manual(texto: str) -> dict:
    """Para ingresar un mensaje copiado manualmente desde WhatsApp."""
    return {
        "fecha": datetime.now(),
        "remitente": "PPI",
        "texto": texto.strip(),
    }
