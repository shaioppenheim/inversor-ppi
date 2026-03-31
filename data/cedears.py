# Tabla de CEDEARs: ticker BYMA → {subyacente US, ratio, sector}
# Ratio = cantidad de CEDEARs que equivalen a 1 acción subyacente
# Actualizado: 2026-03

CEDEARS = {
    # TECNOLOGÍA
    "AAPL":  {"us": "AAPL",  "ratio": 10,  "nombre": "Apple",           "sector": "Tecnología"},
    "MSFT":  {"us": "MSFT",  "ratio": 8,   "nombre": "Microsoft",       "sector": "Tecnología"},
    "GOOGL": {"us": "GOOGL", "ratio": 34,  "nombre": "Alphabet",        "sector": "Tecnología"},
    "AMZN":  {"us": "AMZN",  "ratio": 10,  "nombre": "Amazon",          "sector": "Tecnología"},
    "NVDA":  {"us": "NVDA",  "ratio": 7,   "nombre": "NVIDIA",          "sector": "Tecnología"},
    "META":  {"us": "META",  "ratio": 7,   "nombre": "Meta",            "sector": "Tecnología"},
    "TSLA":  {"us": "TSLA",  "ratio": 9,   "nombre": "Tesla",           "sector": "Automóviles"},
    "NFLX":  {"us": "NFLX",  "ratio": 7,   "nombre": "Netflix",         "sector": "Entretenimiento"},
    "ORCL":  {"us": "ORCL",  "ratio": 5,   "nombre": "Oracle",          "sector": "Tecnología"},
    "AMD":   {"us": "AMD",   "ratio": 3,   "nombre": "AMD",             "sector": "Tecnología"},
    "INTC":  {"us": "INTC",  "ratio": 2,   "nombre": "Intel",           "sector": "Tecnología"},
    "CRM":   {"us": "CRM",   "ratio": 6,   "nombre": "Salesforce",      "sector": "Tecnología"},
    "PYPL":  {"us": "PYPL",  "ratio": 3,   "nombre": "PayPal",          "sector": "Fintech"},
    "SQ":    {"us": "SQ",    "ratio": 4,   "nombre": "Block (Square)",  "sector": "Fintech"},
    # FINANZAS
    "BRKB":  {"us": "BRK-B", "ratio": 5,   "nombre": "Berkshire B",     "sector": "Finanzas"},
    "JPM":   {"us": "JPM",   "ratio": 5,   "nombre": "JPMorgan",        "sector": "Finanzas"},
    "GS":    {"us": "GS",    "ratio": 8,   "nombre": "Goldman Sachs",   "sector": "Finanzas"},
    "BAC":   {"us": "BAC",   "ratio": 2,   "nombre": "Bank of America", "sector": "Finanzas"},
    "V":     {"us": "V",     "ratio": 10,  "nombre": "Visa",            "sector": "Finanzas"},
    "MA":    {"us": "MA",    "ratio": 10,  "nombre": "Mastercard",      "sector": "Finanzas"},
    # ENERGÍA
    "XOM":   {"us": "XOM",   "ratio": 4,   "nombre": "ExxonMobil",      "sector": "Energía"},
    "CVX":   {"us": "CVX",   "ratio": 4,   "nombre": "Chevron",         "sector": "Energía"},
    # CONSUMO
    "MCD":   {"us": "MCD",   "ratio": 8,   "nombre": "McDonald's",      "sector": "Consumo"},
    "KO":    {"us": "KO",    "ratio": 2,   "nombre": "Coca-Cola",       "sector": "Consumo"},
    "DIS":   {"us": "DIS",   "ratio": 4,   "nombre": "Disney",          "sector": "Entretenimiento"},
    "WMT":   {"us": "WMT",   "ratio": 4,   "nombre": "Walmart",         "sector": "Consumo"},
    "MELI":  {"us": "MELI",  "ratio": 200, "nombre": "MercadoLibre",    "sector": "Tecnología"},
    # ETFs
    "SPY":   {"us": "SPY",   "ratio": 14,  "nombre": "S&P 500 ETF",          "sector": "ETF"},
    "QQQ":   {"us": "QQQ",   "ratio": 10,  "nombre": "Nasdaq 100 ETF",       "sector": "ETF"},
    "GLD":   {"us": "GLD",   "ratio": 10,  "nombre": "SPDR Gold Trust",       "sector": "ETF"},
    "XLE":   {"us": "XLE",   "ratio": 10,  "nombre": "Energy Select SPDR",    "sector": "ETF"},
    "XLF":   {"us": "XLF",   "ratio": 10,  "nombre": "Financial Select SPDR", "sector": "ETF"},
    "SMH":   {"us": "SMH",   "ratio": 5,   "nombre": "VanEck Semiconductors", "sector": "ETF"},
    "URA":   {"us": "URA",   "ratio": 5,   "nombre": "Global X Uranium ETF",  "sector": "ETF"},
    "CIBR":  {"us": "CIBR",  "ratio": 5,   "nombre": "First Trust Cybersecurity", "sector": "ETF"},
    "AZN":   {"us": "AZN",   "ratio": 10,  "nombre": "AstraZeneca",           "sector": "Salud"},
    "VIST":  {"us": "VIST",  "ratio": 1,   "nombre": "Vista Energy",          "sector": "Energía"},
}

# Lista de los más líquidos para análisis prioritario
CEDEARS_TOP_LIQUIDOS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRKB", "MELI", "SPY", "QQQ"]
