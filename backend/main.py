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
HUB_PATH = "/app/models"
OLLAMA_URL = "http://ollama_hub:11434"  # Servicio interno Docker

# ---- MODELOS ----
class GenerateRequest(BaseModel):
    model: Literal["yue", "ace-step"] = "yue"
    mode: Literal["creative", "exact", "factory"] = "creative"
    # Modo creativo
    prompt: Optional[str] = None
    style: Optional[str] = None
    genre: Optional[str] = "Cinematic"
    # Modo exacto
    lyrics: Optional[str] = None
    # Fábrica
    batch_title: Optional[str] = None

# ---- ENDPOINTS ----

@app.get("/")
def status():
    gpu_available = torch.cuda.is_available()
    return {
        "status": "DocuMusic Online",
        "engine": "YuE-7B + ACE-Step 1.5",
        "gpu_status": "Active" if gpu_available else "Disconnected",
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else "None",
        "vram_total": f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB" if gpu_available else "0",
        "models_available": ["yue", "ace-step"],
        "modes": ["creative", "exact", "factory"]
    }

@app.post("/generate")
async def generate(req: GenerateRequest):
    """
    Punto de entrada unificado para las 3 modalidades.
    """
    print(f"[DocuMusic] model={req.model} | mode={req.mode} | genre={req.genre}")

    # ---- MODO CREATIVO: La IA desarrolla la idea ----
    if req.mode == "creative":
        if not req.prompt:
            raise HTTPException(400, "Se requiere 'prompt' para el modo creativo.")

        # Paso 1: Generar letra con Ollama (LLaMA3)
        lyrics = await _generate_lyrics_with_ollama(
            prompt=req.prompt,
            style=req.style or "",
            genre=req.genre or "Pop"
        )

        # Paso 2: Musicalizar con el modelo seleccionado
        audio_url = await _musicalize(model=req.model, lyrics=lyrics, genre=req.genre)

        return {
            "status": "success",
            "mode": "creative",
            "model_used": req.model,
            "generated_lyrics": lyrics,
            "audio_url": audio_url,
            "message": f"Composición generada con {req.model.upper()} en modalidad creativa."
        }

    # ---- MODO EXACTO: Respetar letra al 100% ----
    elif req.mode == "exact":
        if not req.lyrics:
            raise HTTPException(400, "Se requiere 'lyrics' para el modo exacto.")

        audio_url = await _musicalize(model=req.model, lyrics=req.lyrics, genre=req.genre, strict=True)

        return {
            "status": "success",
            "mode": "exact",
            "model_used": req.model,
            "audio_url": audio_url,
            "message": f"Letra musicalizada exactamente con {req.model.upper()}."
        }

    # ---- MODO FÁBRICA: Procesamiento en lote ----
    elif req.mode == "factory":
        return {
            "status": "queued",
            "mode": "factory",
            "message": "Tarea añadida a la cola de procesamiento por lotes.",
            "batch_title": req.batch_title or "Sin título"
        }

    raise HTTPException(400, "Modo no reconocido.")


@app.post("/factory/upload")
async def factory_upload(file: UploadFile = File(...)):
    """
    Recibe un archivo .docx con letras y estilos para procesamiento en lote.
    """
    if not file.filename.endswith(('.docx', '.doc')):
        raise HTTPException(400, "Solo se aceptan archivos Word (.docx, .doc)")

    contents = await file.read()
    # Aquí procesaremos el Word con python-docx
    # Por ahora devolvemos una simulación de la cola
    return {
        "status": "queued",
        "filename": file.filename,
        "size_kb": round(len(contents) / 1024, 2),
        "queue": [
            {"id": 1, "title": "Canción 1 (del Word)", "status": "pending"},
            {"id": 2, "title": "Canción 2 (del Word)", "status": "pending"},
            {"id": 3, "title": "Canción 3 (del Word)", "status": "pending"},
        ],
        "message": "Archivo recibido. Procesamiento en lote iniciado."
    }


# ---- FUNCIONES INTERNAS ----

async def _generate_lyrics_with_ollama(prompt: str, style: str, genre: str) -> str:
    """
    Llama a Ollama (LLaMA3) para generar la letra de la canción.
    """
    system_prompt = f"""Eres un compositor profesional de canciones. 
    Estilo: {style}. Género: {genre}.
    Crea una letra completa con [Intro], [Verso 1], [Coro], [Verso 2], [Coro], [Outro].
    Solo responde con la letra, sin explicaciones."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": f"{system_prompt}\n\nIdea: {prompt}",
                "stream": False
            })
            data = res.json()
            return data.get("response", "No se pudo generar la letra.")
    except Exception as e:
        print(f"[Ollama Error] {e}")
        return f"[Verso 1]\nLetra generada para: {prompt}\n[Coro]\nEsperando conexión con Ollama..."


async def _musicalize(model: str, lyrics: str, genre: str, strict: bool = False) -> str:
    """
    Llama al motor de generación musical (YuE o ACE-Step).
    Retorna la URL del archivo de audio generado.
    """
    # Aquí conectaremos con YuE / ACE-Step cuando los modelos estén descargados
    # Por ahora retorna la ruta donde se guardará el audio
    output_path = f"/app/outputs/{model}_{genre.lower()}_output.mp3"
    print(f"[{model.upper()}] Musicalizando {'(strict)' if strict else '(creativo)'} -> {output_path}")
    return f"/outputs/{model}_{genre.lower()}_output.mp3"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
