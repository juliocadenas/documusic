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
    && rm -rf /var/lib/apt/lists/*

# Configurar variables de entorno para compilación de llama-cpp con CUDA
ENV CMAKE_ARGS="-DLLAMA_CUDA=on"
ENV FORCE_CMAKE=1

# Directorio de trabajo
WORKDIR /app

# Copiar requerimientos
COPY requirements.txt .

# Instalar PyTorch con soporte CUDA 12.1
RUN pip3 install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalar el resto de dependencias (esto compilará llama-cpp-python con CUDA)
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir bitsandbytes accelerate

# Copiar el código fuente
COPY . .

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para iniciar el servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
