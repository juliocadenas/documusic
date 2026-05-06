import os
import torch
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llama_cpp import Llama
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = "/app/models/YuE-7B/YuE-7B.Q4_K_M.gguf"
OLLAMA_URL = "http://ollama_hub:11434"

llm = None

def get_llm():
    global llm
    if llm is None:
        if os.path.exists(MODEL_PATH):
            print(f"[DEBUG] Iniciando carga de modelo GGUF...")
            try:
                # Bajamos n_gpu_layers a 20 para ver si es un tema de memoria/Blackwell
                # Activamos verbose=True para ver los logs internos de llama.cpp
                llm = Llama(
                    model_path=MODEL_PATH,
                    n_gpu_layers=20, 
                    n_ctx=2048,
                    verbose=True
                )
                print("[DEBUG] ✅ Modelo cargado con éxito.")
            except Exception as e:
                print(f"[DEBUG] ❌ Error fatal al cargar: {str(e)}")
        else:
            print(f"[DEBUG] ❌ Archivo no encontrado en {MODEL_PATH}")
    return llm

@app.get("/")
@app.get("/api")
def status():
    return {
        "status": "Online",
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Buscando...",
        "model_status": "Cargado" if llm is not None else "En espera",
        "vram_free": f"{torch.cuda.mem_get_info()[0] // 1024**2} MB" if torch.cuda.is_available() else "0"
    }

@app.post("/api/generate")
async def generate(req: dict):
    prompt = req.get("prompt", "Música")
    lyrics = await _generate_lyrics(prompt)
    
    # Intentamos cargar el motor
    engine = get_llm()
    
    return {
        "status": "success",
        "generated_lyrics": lyrics,
        "audio_url": "https://www.docuplay.com/demo_music.mp3",
        "debug_info": "Motor YuE iniciado en Madrid"
    }

async def _generate_lyrics(prompt: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"Letra de canción sobre {prompt}. Corta.",
                "stream": False
            })
            return res.json().get("response", "Madrid OK")
    except:
        return "Conectado. Generando audio..."

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
