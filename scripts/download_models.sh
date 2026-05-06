#!/bin/bash
# Script para descargar los modelos de YuE en el servidor de Madrid
# Ejecutar: bash scripts/download_models.sh

echo "🎵 DocuMusic - Descarga de Modelos YuE"
echo "========================================="
echo "Este proceso descargará ~16GB. Puede tardar 30-60 minutos."
echo ""

MODELS_DIR="$HOME/AI_MODELS/YuE"
mkdir -p "$MODELS_DIR"

# Verificar que huggingface-cli está instalado
if ! command -v huggingface-cli &> /dev/null; then
    echo "📦 Instalando huggingface-hub..."
    pip3 install huggingface-hub
fi

echo "⬇️  Descargando Stage 1 (YuE-s1-7B, ~14GB)..."
huggingface-cli download m-a-p/YuE-s1-7B-anneal-en-cot \
    --local-dir "$MODELS_DIR/YuE-s1" \
    --repo-type model

echo "⬇️  Descargando Stage 2 (YuE-s2-1B, ~2GB)..."
huggingface-cli download m-a-p/YuE-s2-1B-general \
    --local-dir "$MODELS_DIR/YuE-s2" \
    --repo-type model

echo ""
echo "✅ Modelos descargados en: $MODELS_DIR"
echo ""
echo "Ahora actualiza el docker-compose.yml para montar esta carpeta:"
echo "  volumes:"
echo "    - $MODELS_DIR:/app/models"
echo ""
echo "Y reinicia el contenedor:"
echo "  cd ~/documusic && docker compose restart documusic_backend"
