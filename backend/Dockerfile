FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema, audio y herramientas de compilación
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    ffmpeg \
    git \
    cmake \
    ninja-build \
    build-essential \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Actualizar pip
RUN pip3 install --upgrade pip

# Instalar PyTorch con soporte CUDA 12.1
RUN pip3 install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalar llama-cpp-python usando el binario pre-compilado para CUDA 12.1
# Esto evita tener que compilarlo desde cero y es mucho más rápido y seguro
RUN pip3 install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Copiar requerimientos e instalar el resto
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir bitsandbytes accelerate

# Copiar el código fuente
COPY . .

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para iniciar el servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
