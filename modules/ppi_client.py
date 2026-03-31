"""
Cliente para la API de PPI usando la librería oficial ppi_client.
Docs: https://itatppi.github.io/ppi-official-api-docs/api/documentacionPython/
"""

import os
from ppi_client.ppi import PPI


class PPIClient:
    def __init__(self):
        self.client_id = os.getenv("PPI_CLIENT_ID")
        self.client_secret = os.getenv("PPI_CLIENT_SECRET")
        self.account_number = os.getenv("PPI_ACCOUNT_NUMBER")
        self._ppi = None

    @property
    def conectado(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def autenticar(self):
        self._ppi = PPI(sandbox=False)
        self._ppi.account.login_api(self.client_id, self.client_secret)
        return self._ppi

    def _cliente(self):
        if not self._ppi:
            self.autenticar()
        return self._ppi

    def get_cartera(self) -> dict:
        """Retorna la cartera real (rápido). P&L calculado por separado con enriquecer_con_pnl()."""
        data = self._cliente().account.get_balance_and_positions(self.account_number)
        cartera = {}
        for grupo in data.get("groupedInstruments", []):
            tipo = grupo.get("name", "")
            for inst in grupo.get("instruments", []):
                ticker = inst.get("ticker")
                if not ticker:
                    continue
                cartera[ticker] = {
                    "nombre": inst.get("description", ticker),
                    "cantidad": inst.get("quantity", 0),
                    "precio_actual_ars": inst.get("price"),
                    "precio_promedio_ars": None,
                    "valor_total_ars": inst.get("amount"),
                    "pnl_pct": None,
                    "pnl_usd": None,
                    "tipo": tipo,
                }
        return cartera

    def enriquecer_con_pnl(self, cartera: dict) -> dict:
        """
        Enriquece una cartera existente con precio promedio y P&L.
        Llama a la API de movimientos para cada posición — puede tardar 30-60 seg.
        Modifica el dict in-place y también lo retorna.
        """
        for ticker, pos in cartera.items():
            try:
                resultado = self.calcular_precio_promedio(
                    ticker,
                    pos["cantidad"],
                    precio_actual_ars=pos["precio_actual_ars"],
                )
                if resultado:
                    pos["precio_promedio_ars"] = resultado.get("precio_promedio_ars")
                    pos["pnl_pct"] = resultado.get("pnl_pct")
                    pos["pnl_usd"] = resultado.get("pnl_usd")
            except Exception:
                pass
        return cartera

    def get_cartera_cedears(self) -> dict:
        """Retorna solo los CEDEARs."""
        cartera = self.get_cartera()
        return {t: p for t, p in cartera.items() if p["tipo"] == "CEDEARS"}

    def calcular_precio_promedio(self, ticker: str, cantidad_actual: int, precio_actual_ars: float = None) -> dict:
        """
        Calcula precio promedio y P&L desde el historial de movimientos.
        Usa promedio ponderado de compras (quantity > 0).
        precio_actual_ars: precio ARS del CEDEAR (para evitar llamada circular a get_cartera).
        Retorna precio promedio en ARS y P&L %.
        """
        from ppi_client.models.account_movements import AccountMovements
        from datetime import datetime, timedelta
        from modules.market_data import get_ccl_referencia

        mov = AccountMovements(
            self.account_number,
            (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d"),
            ticker,
        )
        try:
            movimientos = self._cliente().account.get_movements(mov)
        except Exception:
            return {}

        if not movimientos:
            return {}

        # Promedio ponderado de compras (quantity > 0, precio en USD por CEDEAR)
        total_cantidad = 0
        total_costo = 0.0
        for m in movimientos:
            qty = m.get("quantity", 0)
            price = m.get("price", 0) or 0
            if qty > 0:  # compra
                total_cantidad += qty
                total_costo += qty * price

        if total_cantidad == 0:
            return {}

        precio_promedio_usd = total_costo / total_cantidad

        # Convertir a ARS usando CCL actual
        ccl = get_ccl_referencia()
        precio_promedio_ars_calc = precio_promedio_usd * ccl if ccl else None

        # P&L usando precio ARS actual (pasado como parámetro para evitar recursión)
        pnl_pct = None
        pnl_usd = None
        precio_actual_usd = None
        if precio_actual_ars and ccl:
            precio_actual_usd = precio_actual_ars / ccl
        if precio_actual_usd and precio_promedio_usd:
            pnl_pct = ((precio_actual_usd / precio_promedio_usd) - 1) * 100
            pnl_usd = (precio_actual_usd - precio_promedio_usd) * cantidad_actual

        return {
            "precio_promedio_usd": round(precio_promedio_usd, 2),
            "precio_promedio_ars": round(precio_promedio_ars_calc) if precio_promedio_ars_calc else None,
            "precio_actual_usd": round(precio_actual_usd, 2) if precio_actual_usd else None,
            "pnl_pct": round(pnl_pct, 1) if pnl_pct is not None else None,
            "pnl_usd": round(pnl_usd, 2) if pnl_usd is not None else None,
        }


# ── Modo demo (sin credenciales PPI) ─────────────────────────────────────────

CARTERA_DEMO = {
    # Precios ARS = precio_USD / ratio * CCL (~1480)
    # AAPL: $248 USD / ratio 10 * 1480 = ~$36,700 ARS por CEDEAR
    "AAPL": {
        "nombre": "Apple Inc.",
        "cantidad": 50,
        "precio_actual_ars": 36_700,
        "precio_promedio_ars": 30_000,
        "valor_total_ars": 1_835_000,
        "pnl_pct": 22.3,
        "tipo": "CEDEAR",
    },
    # MSFT: $390 USD / ratio 8 * 1480 = ~$72,150 ARS por CEDEAR
    "MSFT": {
        "nombre": "Microsoft Corp.",
        "cantidad": 30,
        "precio_actual_ars": 72_150,
        "precio_promedio_ars": 65_000,
        "valor_total_ars": 2_164_500,
        "pnl_pct": 11.0,
        "tipo": "CEDEAR",
    },
    # NVDA: $110 USD / ratio 7 * 1480 = ~$23,200 ARS por CEDEAR
    "NVDA": {
        "nombre": "NVIDIA Corp.",
        "cantidad": 20,
        "precio_actual_ars": 23_200,
        "precio_promedio_ars": 18_000,
        "valor_total_ars": 464_000,
        "pnl_pct": 28.9,
        "tipo": "CEDEAR",
    },
    # MELI: $2000 USD / ratio 200 * 1480 = ~$14,800 ARS por CEDEAR
    "MELI": {
        "nombre": "MercadoLibre Inc.",
        "cantidad": 5,
        "precio_actual_ars": 14_800,
        "precio_promedio_ars": 12_500,
        "valor_total_ars": 74_000,
        "pnl_pct": 18.4,
        "tipo": "CEDEAR",
    },
}


def get_cartera(usar_demo: bool = False) -> dict:
    """
    Obtiene la cartera: real (PPI API) o demo.
    Si no hay credenciales, usa demo automáticamente.
    """
    client = PPIClient()

    if usar_demo or not client.conectado:
        print("⚠️  Sin credenciales PPI — usando cartera demo")
        return CARTERA_DEMO

    try:
        return client.get_cartera()
    except Exception as e:
        print(f"⚠️  Error PPI API: {e} — usando cartera demo")
        return CARTERA_DEMO
