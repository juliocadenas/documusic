FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git cmake ninja-build build-essential libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Actualizar pip e instalar PyTorch Nightly
RUN pip3 install --upgrade pip
RUN pip3 install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# ---- LA OPCIÓN NUCLEAR PARA RTX 5080 (Blackwell) ----

# 1. Engañamos al sistema copiando el stub de CUDA a la carpeta de librerías del sistema
# Esto evita que el linker falle al no encontrar libcuda.so.1 durante el build de Docker
RUN cp /usr/local/cuda/lib64/stubs/libcuda.so /usr/lib/x86_64-linux-gnu/libcuda.so.1

# 2. Configuración de compilación optimizada para sm_120
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF"
ENV FORCE_CMAKE=1

# 3. Instalación de llama-cpp-python
RUN pip3 install llama-cpp-python --no-cache-dir

# 4. Limpiamos el "engaño" para que el contenedor use el driver real al arrancar
RUN rm /usr/lib/x86_64-linux-gnu/libcuda.so.1

# Resto de la instalación
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir bitsandbytes accelerate

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
