#!/bin/bash
# Setup inicial del proyecto
set -e

echo "📦 Instalando dependencias..."
pip install -r requirements.txt

echo "🔧 Creando .env desde template..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env creado — editalo con tus credenciales"
else
    echo "⚠️  .env ya existe, no se sobreescribe"
fi

mkdir -p exports

echo ""
echo "✅ Setup completo!"
echo ""
echo "Próximos pasos:"
echo "  1. Editá .env con tu API key de Anthropic (obligatoria)"
echo "  2. Opcional: agregar credenciales PPI para ver cartera real"
echo "  3. Opcional: agregar API key de Financial Modeling Prep (gratis)"
echo "  4. Ejecutar: streamlit run app.py"
