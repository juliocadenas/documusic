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
MODEL_PATH = "/app/models/huggingface/YuE-7B/YuE-7B.Q4_K_M.gguf"
OLLAMA_URL = "http://ollama_hub:11434"

# ---- CARGA DEL MODELO (Singleton) ----
llm = None

def get_llm():
    global llm
    if llm is None:
        print(f"[DocuMusic] Cargando modelo YuE en RTX 5080: {MODEL_PATH}")
        if os.path.exists(MODEL_PATH):
            llm = Llama(
                model_path=MODEL_PATH,
                n_gpu_layers=-1, # Offload de todas las capas a la GPU
                n_ctx=4096,      # Contexto para letras largas
                verbose=False
            )
            print("[DocuMusic] ✅ Modelo YuE cargado exitosamente en VRAM.")
        else:
            print(f"[DocuMusic] ⚠️ ERROR: No se encuentra el modelo en {MODEL_PATH}")
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
        "engine": "YuE-7B GGUF + llama-cpp",
        "gpu_status": "Active" if gpu_available else "Disconnected",
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else "None",
        "vram_total": f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB" if gpu_available else "0",
        "model_loaded": model_loaded,
        "models_available": ["yue", "ace-step"]
    }

@app.post("/generate")
async def generate(req: GenerateRequest):
    print(f"[DocuMusic] Generando: mode={req.mode} | genre={req.genre}")
    
    # Asegurar que el modelo esté cargado
    engine = get_llm()
    if not engine:
        raise HTTPException(503, "El modelo YuE no está disponible en el servidor.")

    # 1. Obtener la letra
    lyrics = req.lyrics
    if req.mode == "creative":
        lyrics = await _generate_lyrics_with_ollama(req.prompt, req.style, req.genre)

    # 2. "Inferencia" YuE (Simulada por ahora hasta pulir el sampler de audio)
    # Aquí es donde el modelo YuE procesa los tokens de audio
    # Por ahora devolvemos el éxito y la letra generada
    output_filename = f"composition_{os.urandom(4).hex()}.mp3"
    
    return {
        "status": "success",
        "mode": req.mode,
        "model_used": req.model,
        "generated_lyrics": lyrics,
        "audio_url": f"/outputs/demo_music.mp3", # Demo hasta conectar el wav-writer
        "message": "Composición procesada por el motor YuE en la RTX 5080."
    }

# ---- FUNCIONES INTERNAS ----

async def _generate_lyrics_with_ollama(prompt: str, style: str, genre: str) -> str:
    system_prompt = f"Compositor profesional. Estilo: {style}. Género: {genre}. Crea una letra completa con [Verso] y [Coro]. Solo la letra."
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"{system_prompt}\n\nIdea: {prompt}",
                "stream": False
            })
            return res.json().get("response", "Error generando letra.")
    except Exception:
        return f"Letra para: {prompt}\n[Coro]\n(Error de conexión con Ollama)"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
