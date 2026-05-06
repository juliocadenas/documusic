import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def status():
    return {
        "status": "DocuMusic Online (Debug Mode)",
        "gpu": "RTX 5080 Detectada",
        "message": "Conectividad OK. El 502 debería desaparecer ahora."
    }

@app.post("/generate")
async def generate(req: dict):
    return {
        "status": "success",
        "generated_lyrics": "Probando conectividad... Si ves esto, el túnel está perfecto.",
        "audio_url": None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
