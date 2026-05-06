#!/bin/bash

# ─────────────────────────────────────────────────────────────────────────────
# DocuMusic Factory — Setup Automático para Pop!_OS / Ubuntu + RTX 5080
# ─────────────────────────────────────────────────────────────────────────────

set -e
echo ""
echo "🎵 DOCUMUSIC FACTORY — Multi-Engine AI Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Actualizar sistema
echo "📦 [1/6] Actualizando sistema..."
sudo apt update -y && sudo apt upgrade -y

# 2. Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 [2/6] Instalando Docker..."
    sudo apt install -y docker.io docker-compose curl
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
    echo "✅ Docker instalado."
else
    echo "✅ [2/6] Docker ya está instalado."
fi

# 3. NVIDIA Container Toolkit (GPU passthrough para Docker)
if ! command -v nvidia-ctk &> /dev/null; then
    echo "🎮 [3/6] Instalando NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt update
    sudo apt install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    echo "✅ NVIDIA Container Toolkit configurado."
else
    echo "✅ [3/6] NVIDIA Container Toolkit ya instalado."
fi

# 4. Verificar GPU
echo ""
echo "🔍 [4/6] Verificando GPU disponible..."
if nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo ""
else
    echo "⚠️  No se detectó GPU NVIDIA. El sistema funcionará en modo CPU."
fi

# 5. Pre-pull de imagen Docker (descarga pesada)
echo "⬇️  [5/6] Descargando imagen base de PyTorch + CUDA (puede tardar)..."
docker pull pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# 6. Levantar la plataforma
echo ""
echo "⚡ [6/6] Levantando DocuMusic Factory..."
docker-compose up --build -d

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 ¡DOCUMUSIC FACTORY está corriendo!"
echo ""
echo "  🌐 Frontend:    http://localhost:5173"
echo "  ⚙️  Backend API: http://localhost:8000"
echo "  📖 Docs API:    http://localhost:8000/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 PRIMER USO:"
echo "   1. Abre http://localhost:5173"
echo "   2. En el panel de motores, haz clic en YuE o ACE-Step para activarlo"
echo "   3. La primera vez descargará el modelo (~7-14 GB), ten paciencia"
echo "   4. ¡Genera tu primera canción!"
echo ""
echo "⚠️  NOTA: Si fue tu primera instalación de Docker,"
echo "   ejecuta: newgrp docker (o cierra y abre la terminal)"
echo "   y luego vuelve a correr: docker-compose up -d"
echo ""
