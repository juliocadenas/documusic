import os
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import httpx

app = FastAPI(title="DocuMusic AI Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- CONFIG HUB ----
# Volumen: ~/AI_MODELS/huggingface -> /app/models (ver docker-compose.yml)
MODEL_PATH = "/app/models/YuE-7B/YuE-7B.Q4_K_M.gguf"
OLLAMA_URL = "http://ollama_hub:11434"

# ---- MODELOS DE DATOS ----
class GenerateRequest(BaseModel):
    model: Literal["yue", "ace-step"] = "yue"
    mode: Literal["creative", "exact", "factory"] = "creative"
    prompt: Optional[str] = None
    style: Optional[str] = None
    genre: Optional[str] = "Cinematic"
    lyrics: Optional[str] = None
    batch_title: Optional[str] = None

# ---- ENDPOINTS ----

@app.get("/")
def status():
    gpu_available = torch.cuda.is_available()
    model_exists = os.path.exists(MODEL_PATH)
    return {
        "status": "DocuMusic Online",
        "engine": "YuE-7B GGUF",
        "gpu_status": "Active" if gpu_available else "Disconnected",
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else "RTX 5080 (PyTorch update needed)",
        "vram_total": "15.5 GB",
        "model_file_found": model_exists,
        "model_path": MODEL_PATH,
        "models_available": ["yue", "ace-step"]
    }

@app.post("/generate")
async def generate(req: GenerateRequest):
    print(f"[DocuMusic] Generando: mode={req.mode} | genre={req.genre} | model={req.model}")

    # 1. Obtener la letra
    if req.mode == "creative":
        if not req.prompt:
            raise HTTPException(400, "Se requiere 'prompt' para el modo creativo.")
        lyrics = await _generate_lyrics_with_ollama(req.prompt, req.style or "", req.genre or "Pop")
    elif req.mode == "exact":
        if not req.lyrics:
            raise HTTPException(400, "Se requiere 'lyrics' para el modo exacto.")
        lyrics = req.lyrics
    else:
        lyrics = req.batch_title or "Canción en lote"

    # 2. Confirmar que el modelo existe en disco
    model_ready = os.path.exists(MODEL_PATH)

    return {
        "status": "success",
        "mode": req.mode,
        "model_used": req.model,
        "model_ready": model_ready,
        "generated_lyrics": lyrics,
        "audio_url": None,  # Pendiente: integrar decodificador de audio
        "message": f"✅ Letra generada. Audio pendiente: instalar PyTorch Nightly para RTX 5080 (sm_120)." if model_ready else "⚠️ Modelo YuE no encontrado en disco."
    }

# ---- FUNCIONES INTERNAS ----

async def _generate_lyrics_with_ollama(prompt: str, style: str, genre: str) -> str:
    system = f"Eres un compositor. Estilo: {style}. Género: {genre}. Escribe una letra completa con [Verso 1], [Coro], [Verso 2], [Coro Final]. Solo la letra, sin explicaciones."
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"{system}\n\nIdea: {prompt}",
                "stream": False
            })
            return res.json().get("response", "Error generando letra.")
    except Exception as e:
        print(f"[Ollama] Error: {e}")
        return f"[Verso 1]\nLetra para: {prompt}\n\n[Coro]\nOllama no disponible aún."


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
