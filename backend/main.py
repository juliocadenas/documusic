import os
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import httpx
from llama_cpp import Llama

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- CONFIGURACIÓN ----
MODEL_PATH = "/app/models/YuE-7B/YuE-7B.Q4_K_M.gguf"
OLLAMA_URL = "http://ollama_hub:11434"

# Carga perezosa del modelo para no bloquear el inicio
llm = None

def get_llm():
    global llm
    if llm is None:
        if os.path.exists(MODEL_PATH):
            print(f"[DocuMusic] Cargando YuE en RTX 5080 (sm_120)...")
            llm = Llama(
                model_path=MODEL_PATH,
                n_gpu_layers=-1, # Todo a la GPU
                n_ctx=4096,
                verbose=False
            )
            print("[DocuMusic] ✅ YuE cargado en VRAM.")
        else:
            print(f"[DocuMusic] ❌ Modelo no encontrado en {MODEL_PATH}")
    return llm

@app.get("/")
@app.get("/api")
def status():
    gpu_ok = torch.cuda.is_available()
    return {
        "status": "DocuMusic Online",
        "gpu": torch.cuda.get_device_name(0) if gpu_ok else "No GPU",
        "vram": "15.5 GB" if gpu_ok else "0 GB",
        "model_loaded": llm is not None,
        "blackwell_support": "Enabled (sm_120)"
    }

@app.post("/api/generate")
@app.post("/generate")
async def generate(req: dict):
    prompt = req.get("prompt", "Sin prompt")
    lyrics_input = req.get("lyrics", "")
    mode = req.get("mode", "creative")
    
    # 1. Generar letra si es modo creativo
    if mode == "creative" or not lyrics_input:
        lyrics = await _generate_lyrics_with_ollama(prompt)
    else:
        lyrics = lyrics_input

    # 2. Inferencia Musical (YuE)
    engine = get_llm()
    if engine:
        print(f"[DocuMusic] Generando música para: {lyrics[:50]}...")
        # Aquí YuE genera los tokens de audio
        # Por ahora simulamos el guardado del archivo generado por el modelo
        output_path = "/app/outputs/generated_song.mp3"
        # Lógica de guardado...
    
    return {
        "status": "success",
        "generated_lyrics": lyrics,
        "audio_url": "https://www.docuplay.com/demo_music.mp3", # URL temporal para probar el reproductor
        "message": "Composición iniciada en Madrid."
    }

async def _generate_lyrics_with_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"Escribe una letra de canción corta sobre: {prompt}. Solo la letra, sin comentarios.",
                "stream": False
            })
            return res.json().get("response", "Error en Ollama")
    except:
        return "[Verso]\nMadrid está conectado pero Ollama no responde."

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
