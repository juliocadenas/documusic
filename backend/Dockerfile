FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema y herramientas de compilación
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git cmake ninja-build build-essential libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Actualizar pip e instalar PyTorch Nightly
RUN pip3 install --upgrade pip
RUN pip3 install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# ---- CONFIGURACIÓN AVANZADA PARA RTX 5080 (Blackwell) ----

# 1. Crear enlace simbólico para libcuda.so.1 (la "librería fantasma")
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1

# 2. Configurar variables de entorno para la compilación
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH}
ENV CMAKE_ARGS="-DGGML_CUDA=on \
                -DCMAKE_CUDA_ARCHITECTURES=120 \
                -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs \
                -DLLAMA_BUILD_TESTS=OFF \
                -DLLAMA_BUILD_EXAMPLES=OFF"
ENV FORCE_CMAKE=1

# 3. Instalar llama-cpp-python con las rutas de enlace forzadas
RUN LDFLAGS="-L/usr/local/cuda/lib64/stubs -Wl,-rpath-link,/usr/local/cuda/lib64/stubs" \
    pip3 install llama-cpp-python --no-cache-dir

# Resto de la instalación
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir bitsandbytes accelerate

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
