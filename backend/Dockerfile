FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Dependencias del sistema (incluido git-lfs para el repo de YuE)
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git git-lfs cmake ninja-build build-essential \
    libopenblas-dev libsndfile1 sox wget curl \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Actualizar pip
RUN pip3 install --upgrade pip

# PyTorch Nightly con soporte CUDA 12.8 (RTX 5080 Blackwell)
RUN pip3 install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Dependencias de YuE (motor de música con voces)
RUN pip3 install \
    transformers==4.46.3 \
    accelerate \
    sentencepiece \
    einops \
    encodec \
    soundfile \
    scipy \
    numpy \
    omegaconf

# Clonar YuE
RUN git clone https://github.com/multimodal-art-projection/YuE.git /opt/YuE

# Inicializar submódulos (xcodec_mini_infer es un submódulo de Git)
RUN cd /opt/YuE && git submodule update --init --recursive || true

# Fallback: si el submódulo sigue vacío, clonar xcodec_mini_infer directamente
RUN if [ ! -f /opt/YuE/inference/xcodec_mini_infer/models/soundstream_hubert_new.py ]; then \
        echo "⚠️ Submódulo vacío, clonando xcodec_mini_infer manualmente..."; \
        rm -rf /opt/YuE/inference/xcodec_mini_infer; \
        git clone https://github.com/multimodal-art-projection/xcodec_mini_infer.git /opt/YuE/inference/xcodec_mini_infer; \
    fi

# Verificar que models/ existe
RUN ls -la /opt/YuE/inference/xcodec_mini_infer/ && \
    ls -la /opt/YuE/inference/xcodec_mini_infer/models/ || echo "❌ models/ no encontrado"

# Instalar dependencias adicionales de YuE
RUN cd /opt/YuE && pip3 install -r requirements.txt || true

# API Framework
RUN pip3 install fastapi uvicorn httpx python-multipart

# Opción Nuclear: stub para llama-cpp (si se necesita en el futuro)
RUN cp /usr/local/cuda/lib64/stubs/libcuda.so /usr/lib/x86_64-linux-gnu/libcuda.so.1 && \
    pip3 install llama-cpp-python --no-cache-dir || echo "llama-cpp optional, skipping" && \
    rm -f /usr/lib/x86_64-linux-gnu/libcuda.so.1

# Copiar código del backend
COPY . .

# Crear carpetas necesarias
RUN mkdir -p /app/outputs /app/tmp

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
