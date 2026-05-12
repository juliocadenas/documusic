import os
import glob
import uuid
import subprocess
import threading
import re
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OUTPUT_DIR = "/app/outputs"
MODELS_DIR = "/app/models"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("/app/tmp", exist_ok=True)

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
jobs = {}

@app.get("/")
@app.get("/api")
def status():
    return {"status": "Online", "gpu": "RTX 5080", "yue_ready": True}

@app.post("/api/generate")
async def generate(req: dict, background_tasks: BackgroundTasks):
    lyrics = req.get("lyrics", "")
    style_prompt = req.get("style_prompt", "pop")
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "processing", "logs": ["Iniciando motor YuE 7B..."]}
    background_tasks.add_task(run_yue_inference, job_id, lyrics, style_prompt)
    # CRITICO: model_status="generating" activa el polling en el frontend
    return {"status": "success", "job_id": job_id, "model_status": "generating"}

def run_yue_inference(job_id: str, lyrics: str, style_prompt: str):
    try:
        tmp_dir = f"/app/tmp/{job_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        # --- FIX CRITICO: Formateo correcto de letras para YuE ---
        formatted_lyrics = lyrics.strip()

        # 1. Eliminar tags no estandar como [Repeticion final], [Final], etc.
        formatted_lyrics = re.sub(
            r'\[(?!verse\b|chorus\b|bridge\b|intro\b|outro\b)[^\]]+\]',
            '', formatted_lyrics, flags=re.IGNORECASE
        ).strip()

        # 2. Verificar secciones validas YuE
        has_sections = any(
            tag in formatted_lyrics.lower()
            for tag in ['[verse]', '[chorus]', '[bridge]', '[intro]', '[outro]']
        )

        if not has_sections:
            # Crear MINIMO 2 secciones - sin esto Stage1 genera 0it
            lines = [l.strip() for l in formatted_lyrics.split('\n') if l.strip()]
            if not lines:
                lines = ['Docuplay music platform', 'Learning through music']
            mid = max(1, len(lines) // 2)
            verse = '\n'.join(lines[:mid])
            chorus = '\n'.join(lines[mid:] if len(lines) > mid else lines[:mid])
            formatted_lyrics = f"[verse]\n{verse}\n\n[chorus]\n{chorus}\n\n"

        jobs[job_id]["logs"].append(f"Letras listas: {len(formatted_lyrics)} chars, 2+ secciones")

        l_path = f"{tmp_dir}/lyrics.txt"
        s_path = f"{tmp_dir}/style.txt"
        with open(l_path, "w") as f:
            f.write(formatted_lyrics)
        with open(s_path, "w") as f:
            f.write(style_prompt)

        output_path = f"{OUTPUT_DIR}/{job_id}"
        os.makedirs(output_path, exist_ok=True)

        yue_inference_dir = "/opt/YuE/inference"
        config_path = f"{yue_inference_dir}/xcodec_mini_infer/final_ckpt/config.yaml"
        ckpt_path = f"{yue_inference_dir}/xcodec_mini_infer/final_ckpt/ckpt_00360000.pth"

        cmd = [
            "python3", "-u", "infer.py",
            "--stage1_model", f"{MODELS_DIR}/YuE-s1",
            "--stage2_model", f"{MODELS_DIR}/YuE-s2",
            "--genre_txt", s_path,
            "--lyrics_txt", l_path,
            "--output_dir", output_path,
            "--cuda_idx", "0",
            "--max_new_tokens", "3000",
            "--run_n_segments", "2",
            "--basic_model_config", config_path,
            "--resume_path", ckpt_path,
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = (
            f"{yue_inference_dir}:{yue_inference_dir}/xcodec_mini_infer:"
            f"{yue_inference_dir}/xcodec_mini_infer/models:{yue_inference_dir}/vocos"
        )
        env["ATTENTION_IMPLEMENTATION"] = "eager"
        env["USE_FLASH_ATTN"] = "0"
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        env["PYTHONUNBUFFERED"] = "1"

        jobs[job_id]["logs"].append("Lanzando proceso en GPU RTX 5080...")

        def capture_logs(process, job_id, output_path):
            try:
                for line in process.stdout:
                    clean = line.strip()
                    if clean:
                        print(f"[{job_id}] {clean}", flush=True)
                        jobs[job_id]["logs"].append(clean)

                process.wait()
                if process.returncode == 0:
                    jobs[job_id]["logs"].append("Convirtiendo a MP3...")
                    wavs = glob.glob(f"{output_path}/**/*.wav", recursive=True)
                    if not wavs:
                        wavs = glob.glob(f"{output_path}/*.wav")
                    if wavs:
                        mp3_path = f"{OUTPUT_DIR}/{job_id}.mp3"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", wavs[0], "-b:a", "192k", mp3_path],
                            check=True
                        )
                        jobs[job_id].update({
                            "status": "done",
                            "audio_url": f"/outputs/{job_id}.mp3"
                        })
                        jobs[job_id]["logs"].append("Cancion lista!")
                    else:
                        jobs[job_id].update({"status": "error", "error": "No se encontro WAV"})
                else:
                    jobs[job_id].update({
                        "status": "error",
                        "error": f"Proceso fallo con codigo {process.returncode}"
                    })
            except Exception as e:
                print(f"Error en hilo: {e}", flush=True)
                jobs[job_id].update({"status": "error", "error": str(e)})

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=yue_inference_dir,
            env=env,
            bufsize=1,
            universal_newlines=True
        )

        t = threading.Thread(target=capture_logs, args=(process, job_id, output_path))
        t.daemon = True
        t.start()

    except Exception as e:
        print(f"[YuE] Error critico: {e}", flush=True)
        jobs[job_id].update({"status": "error", "error": str(e)})

@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
