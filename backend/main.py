from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "success", "message": "CONECTADO A MADRID"}

@app.get("/api")
def api_root():
    return {"status": "success", "message": "API MADRID OK"}

@app.post("/api/generate")
@app.post("/generate")
def generate(req: dict):
    return {
        "status": "success", 
        "generated_lyrics": "LA CONEXIÓN FUNCIONA. MADRID ESTÁ VIVO.",
        "audio_url": None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
