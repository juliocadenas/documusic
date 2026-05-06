import os
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import httpx
from llama_cpp import Llama

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

# ---- CARGA DEL MODELO (Singleton) ----
llm = None

def get_llm():
    global llm
    if llm is None:
        print(f"[DocuMusic] Intentando cargar modelo YuE en Blackwell GPU (RTX 5080)...")
        if os.path.exists(MODEL_PATH):
            try:
                llm = Llama(
                    model_path=MODEL_PATH,
                    n_gpu_layers=-1, # Offload total a la GPU
                    n_ctx=4096,
                    verbose=True
                )
                print("[DocuMusic] ✅ ¡ÉXITO! Modelo YuE cargado en VRAM de la RTX 5080.")
            except Exception as e:
                print(f"[DocuMusic] ❌ Error cargando modelo: {e}")
                llm = None
        else:
            print(f"[DocuMusic] ⚠️ Archivo no encontrado en: {MODEL_PATH}")
    return llm

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
    model_loaded = llm is not None
    return {
        "status": "DocuMusic Online",
        "engine": "YuE-7B GGUF + Llama-CPP (Blackwell Ready)",
        "gpu_status": "Active" if gpu_available else "Disconnected",
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else "RTX 5080 (Check Drivers)",
        "vram_total": "15.5 GB",
        "model_loaded": model_loaded,
        "models_available": ["yue", "ace-step"]
    }

@app.post("/generate")
async def generate(req: GenerateRequest):
    print(f"[DocuMusic] Generando: mode={req.mode} | genre={req.genre}")
    
    # Asegurar que el modelo esté cargado
    engine = get_llm()
    
    # 1. Obtener la letra
    if req.mode == "creative":
        lyrics = await _generate_lyrics_with_ollama(req.prompt, req.style or "", req.genre or "Pop")
    else:
        lyrics = req.lyrics or "Sin letra proporcionada"

    # 2. Inferencia simulada (hasta conectar el sampler de audio)
    output_filename = f"composition_{os.urandom(4).hex()}.mp3"
    
    return {
        "status": "success",
        "mode": req.mode,
        "model_used": req.model,
        "model_loaded": engine is not None,
        "generated_lyrics": lyrics,
        "audio_url": f"/outputs/demo_music.mp3",
        "message": "Motor YuE activo en la RTX 5080." if engine else "Letra generada (Motor de audio en espera)."
    }

# ---- FUNCIONES INTERNAS ----

async def _generate_lyrics_with_ollama(prompt: str, style: str, genre: str) -> str:
    system = f"Eres un compositor profesional. Estilo: {style}. Género: {genre}. Escribe una letra completa. Solo la letra."
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"{system}\n\nIdea: {prompt}",
                "stream": False
            })
            return res.json().get("response", "Error generando letra.")
    except Exception:
        return f"[Verso]\nLetra para: {prompt}\n(Ollama offline)"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
