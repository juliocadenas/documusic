FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema y herramientas de compilación
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

# Actualizar pip e instalar PyTorch Nightly para soporte RTX 5080 (sm_120)
RUN pip3 install --upgrade pip
RUN pip3 install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# Configurar variables para compilar llama-cpp-python específicamente para Blackwell
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120"
ENV FORCE_CMAKE=1

# Instalar llama-cpp-python compilando desde fuente con soporte sm_120
RUN pip3 install llama-cpp-python --no-cache-dir

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
