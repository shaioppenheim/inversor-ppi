#!/bin/bash
# Ejecuta el dashboard con el Python correcto del venv
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Verificar .env
if [ ! -f .env ]; then
    echo "⚠️  No existe .env — copiando template..."
    cp .env.example .env
    echo "✅ Editá .env con tu ANTHROPIC_API_KEY antes de continuar"
    exit 1
fi

# Verificar API key
if ! grep -q "ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then
    echo "⚠️  ANTHROPIC_API_KEY no configurada en .env"
    echo "   Obtener en: https://console.anthropic.com"
fi

echo "🚀 Iniciando dashboard..."
"$DIR/venv/bin/python3.11" -m streamlit run app.py --server.port 8501
