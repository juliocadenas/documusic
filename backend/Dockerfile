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

# ============================================================
# HeartMuLa — The Most Powerful Open-Source Music Generation Model
# ============================================================
RUN git clone https://github.com/HeartMuLa/heartlib.git /opt/heartlib && \
    cd /opt/heartlib && pip3 install -e .

# Download HeartMuLa checkpoints (HeartMuLaGen + HeartMuLa-oss-3B + HeartCodec-oss)
RUN mkdir -p /app/models/HeartMuLa && \
    cd /app/models/HeartMuLa && \
    pip3 install huggingface_hub && \
    hf download --local-dir '.' 'HeartMuLa/HeartMuLaGen' && \
    hf download --local-dir './HeartMuLa-oss-3B' 'HeartMuLa/HeartMuLa-oss-3B-happy-new-year' && \
    hf download --local-dir './HeartCodec-oss' 'HeartMuLa/HeartCodec-oss-20260123' || echo "⚠️ HeartMuLa checkpoints download failed - will retry at runtime"

# ============================================================
# DiffRhythm2 — Block Flow Matching Music Generation
# ============================================================
RUN pip3 install \
    torchdiffeq \
    g2p_en \
    pydub \
    muq \
    pedalboard \
    safetensors

# Patch torchaudio CUDA version check (PyTorch nightly may report different CUDA version than torchaudio)
RUN TA_UTILS=$(python3 -c "import torchaudio._extension.utils as u; print(u.__file__)" 2>/dev/null) && \
    if [ -n "$TA_UTILS" ]; then \
    python3 -c "
import re
f='$TA_UTILS'
lines=open(f).readlines(); new=[]; skip=False; ind=0
for l in lines:
    if l.strip().startswith('def _check_cuda_version('):
        ind=len(l)-len(l.lstrip()); new.append(l); new.append(' '*(ind+4)+'pass\n'); skip=True; continue
    if skip:
        if l.strip()=='' or (len(l)-len(l.lstrip())>ind): continue
        else: skip=False
    new.append(l)
open(f,'w').writelines(new); print('patched',f)
" || echo "torchaudio patch skipped"; fi

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
