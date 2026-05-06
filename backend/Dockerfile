FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git cmake ninja-build build-essential \
    libopenblas-dev libsndfile1 sox wget curl \
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

# Clonar el repositorio oficial de YuE
RUN git clone https://github.com/multimodal-art-projection/YuE.git /app/YuE

# Instalar dependencias adicionales de YuE
RUN cd /app/YuE && pip3 install -r requirements.txt || true

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
