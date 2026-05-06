import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

app = FastAPI(title="DocuMusic AI Engine")

# Configuración de Rutas Compartidas (HUB)
MODEL_PATH = "/app/models/YuE-7B"  # Mapeado al Hub central

# 1. Configuración de Cuantización para aprovechar la RTX 5080
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)

print("--- Cargando Motor Musical YuE (Cuantizado 4-bit) ---")
try:
    # Aquí cargaremos el modelo YuE una vez descargado en el Hub
    # tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    # model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, quantization_config=quant_config, device_map="auto")
    print("Motor preparado para carga en GPU 0")
except Exception as e:
    print(f"Error cargando modelos: {e}")

class MusicRequest(BaseModel):
    prompt: str
    duration: int = 30
    genre: str = "lo-fi"

@app.get("/")
def read_root():
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "No GPU found"
    return {"status": "DocuMusic Online", "gpu": gpu_name}

@app.post("/generate-music")
async def generate_music(request: MusicRequest):
    # Lógica para llamar a YuE y ACE-Step
    return {"message": "Iniciando generación musical...", "prompt": request.prompt}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
