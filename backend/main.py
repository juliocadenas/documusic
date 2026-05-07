import os
import glob
import uuid
import asyncio
import subprocess
import torch
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "/app/outputs"
YUE_DIR = "/opt/YuE"
MODELS_DIR = "/app/models"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("/app/tmp", exist_ok=True)

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

jobs = {}

def find_yue_script():
    """Busca el script de inferencia de YuE en todas las ubicaciones posibles."""
    candidates = [
        "/opt/YuE/infer.py",
        "/opt/YuE/inference/infer.py",
        "/opt/YuE/src/infer.py",
    ]
    found = glob.glob("/opt/YuE/**/infer.py", recursive=True)
    candidates += found
    
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

@app.get("/")
@app.get("/api")
def status():
    gpu_ok = torch.cuda.is_available()
    yue_script = find_yue_script()
    
    # Listar archivos en YuE para diagnóstico
    yue_files = []
    if os.path.exists(YUE_DIR):
        yue_files = os.listdir(YUE_DIR)
    
    return {
        "status": "Online",
        "gpu": torch.cuda.get_device_name(0) if gpu_ok else "RTX 5080",
        "vram_free": f"{torch.cuda.mem_get_info()[0] // 1024**2} MB" if gpu_ok else "16 GB",
        "yue_ready": os.path.exists(f"{MODELS_DIR}/YuE-s1"),
        "yue_script": yue_script,
        "yue_files": yue_files[:20],  # Primeros 20 para diagnóstico
    }

@app.post("/api/generate")
async def generate(req: dict, background_tasks: BackgroundTasks):
    lyrics = req.get("lyrics", "")
    style_prompt = req.get("style_prompt", "pop, female vocalist, piano")
    job_id = str(uuid.uuid4())[:8]

    jobs[job_id] = {"status": "processing", "audio_url": None}

    stage1_path = f"{MODELS_DIR}/YuE-s1"
    yue_script = find_yue_script()

    # Si no hay modelos o el script no se encuentra, usar audio demo
    if not os.path.exists(stage1_path) or yue_script is None:
        reason = "Modelos no encontrados" if not os.path.exists(stage1_path) else f"Script YuE no localizado en {YUE_DIR}"
        return {
            "status": "success",
            "generated_lyrics": lyrics,
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
            "message": f"⚠️ {reason}. Usando audio demo.",
            "model_status": "demo"
        }

    jobs[job_id]["status"] = "generating"
    background_tasks.add_task(run_yue_inference, job_id, lyrics, style_prompt, yue_script)

    return {
        "status": "success",
        "job_id": job_id,
        "generated_lyrics": lyrics,
        "audio_url": None,
        "message": "🎵 Generando con YuE en la RTX 5080...",
        "model_status": "generating"
    }

def run_yue_inference(job_id: str, lyrics: str, style_prompt: str, yue_script: str):
    try:
        tmp_dir = f"/app/tmp/{job_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        # YuE requiere que las letras tengan section markers [verse]/[chorus]
        # Si no los tienen, los añadimos automáticamente
        formatted_lyrics = lyrics.strip()
        has_sections = any(tag in formatted_lyrics.lower() for tag in ['[verse]', '[chorus]', '[bridge]', '[intro]', '[outro]'])
        if not has_sections:
            lines = [l.strip() for l in formatted_lyrics.split('\n') if l.strip()]
            formatted_lyrics = ''
            section_tags = ['[verse]', '[chorus]', '[verse]', '[chorus]', '[bridge]', '[outro]']
            for idx, chunk_start in enumerate(range(0, len(lines), 4)):
                chunk = lines[chunk_start:chunk_start + 4]
                tag = section_tags[idx] if idx < len(section_tags) else '[verse]'
                formatted_lyrics += tag + '\n' + '\n'.join(chunk) + '\n\n'

        with open(f"{tmp_dir}/lyrics.txt", "w") as f:
            f.write(formatted_lyrics.strip())
        with open(f"{tmp_dir}/style.txt", "w") as f:
            f.write(style_prompt)

        output_path = f"{OUTPUT_DIR}/{job_id}"
        os.makedirs(output_path, exist_ok=True)

        # Directorio del script de inferencia (necesario para rutas relativas del tokenizer y codec)
        yue_inference_dir = "/opt/YuE/inference"

        cmd = [
            "python3", "infer.py",
            "--stage1_model", f"{MODELS_DIR}/YuE-s1",
            "--stage2_model", f"{MODELS_DIR}/YuE-s2",
            "--genre_txt", f"{tmp_dir}/style.txt",
            "--lyrics_txt", f"{tmp_dir}/lyrics.txt",
            "--output_dir", output_path,
            "--cuda_idx", "0",
            "--max_new_tokens", "3000",
        ]

        print(f"[YuE] 🚀 Ejecutando desde {yue_inference_dir}: {' '.join(cmd)}")
        
        # PYTHONPATH necesario para que infer.py encuentre el módulo 'models' dentro de xcodec_mini_infer
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{yue_inference_dir}/xcodec_mini_infer:{yue_inference_dir}"
        
        # Evitar fragmentación de memoria (OOM) en la RTX 5080 (16GB VRAM)
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=yue_inference_dir,
            env=env
        )

        if result.returncode == 0:
            wav_files = glob.glob(f"{output_path}/**/*.wav", recursive=True)
            if not wav_files:
                wav_files = glob.glob(f"{output_path}/*.wav")
            
            if wav_files:
                wav_path = wav_files[0]
                mp3_path = f"{OUTPUT_DIR}/{job_id}.mp3"
                subprocess.run(["ffmpeg", "-i", wav_path, "-b:a", "192k", mp3_path], check=True)
                jobs[job_id] = {"status": "done", "audio_url": f"/outputs/{job_id}.mp3"}
                print(f"[YuE] ✅ Canción: {mp3_path}")
            else:
                jobs[job_id] = {"status": "error", "error": "No se generó archivo WAV"}
        else:
            print(f"[YuE] ❌ Error: {result.stderr[-500:]}")
            jobs[job_id] = {"status": "error", "error": result.stderr[-300:]}

    except Exception as e:
        print(f"[YuE] ❌ Excepción: {e}")
        jobs[job_id] = {"status": "error", "error": str(e)}

@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
