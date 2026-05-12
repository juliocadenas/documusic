import paramiko
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print(f"[1/6] Conectando a {HOST}...")
client.connect(HOST, username=USER, password=PASS, timeout=15)
print("      ✅ Conectado!")

def run(cmd, timeout=120, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    combined = (out + err).strip()
    if show and combined:
        for line in combined.split('\n'):
            print(f"      {line}")
    return combined

# ─────────────────────────────────────────────────────
# PASO 1: Verificar estado del driver GPU en el HOST
# ─────────────────────────────────────────────────────
print("\n[2/6] Estado del driver GPU (host)...")
result = run("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1")
if "ERR!" in result or "failed" in result.lower() or not result:
    print("\n  ⚠️  ADVERTENCIA: El driver de la RTX 5080 sigue en estado ERR!")
    print("  ⚠️  El servidor NECESITA un reinicio completo (sudo reboot)")
    print("  ⚠️  Después del reinicio, corre este script de nuevo.")
    client.close()
    sys.exit(1)
else:
    print(f"  ✅ GPU OK: {result.strip()}")

# ─────────────────────────────────────────────────────
# PASO 2: Instalar dependencias del sistema
# ─────────────────────────────────────────────────────
print("\n[3/6] Verificando dependencias del sistema...")
run("which git python3 pip3 2>&1")

# ─────────────────────────────────────────────────────
# PASO 3: Clonar / actualizar ACE-Step
# ─────────────────────────────────────────────────────
print("\n[4/6] Clonando ACE-Step...")

check = run("test -d /home/pepe/acestep && echo EXISTS || echo MISSING", show=False)
if "EXISTS" in check:
    print("      📁 /home/pepe/acestep ya existe, actualizando...")
    run("cd /home/pepe/acestep && git pull 2>&1", timeout=60)
else:
    print("      📥 Clonando repositorio ACE-Step...")
    result = run("git clone https://github.com/ace-step/ACE-Step.git /home/pepe/acestep 2>&1", timeout=120)
    if "error" in result.lower() and "already exists" not in result.lower():
        print("  ❌ Error al clonar. Verificar conexión a internet.")
        client.close()
        sys.exit(1)
    print("      ✅ Repositorio clonado!")

# ─────────────────────────────────────────────────────
# PASO 4: Crear entorno virtual e instalar dependencias
# ─────────────────────────────────────────────────────
print("\n[5/6] Instalando dependencias de ACE-Step...")

setup_cmds = """
cd /home/pepe/acestep
python3 -m venv venv 2>&1 || true
source venv/bin/activate
pip install --upgrade pip --quiet
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 --quiet 2>&1 | tail -3
pip install -e . --quiet 2>&1 | tail -5
echo "INSTALL_DONE"
"""
result = run(setup_cmds, timeout=600)
if "INSTALL_DONE" in result:
    print("      ✅ Dependencias instaladas!")
else:
    print("      ⚠️  Instalación puede no haber completado. Revisa manualmente.")

# ─────────────────────────────────────────────────────
# PASO 5: Subir el backend FastAPI para ACE-Step
# ─────────────────────────────────────────────────────
print("\n[6/6] Subiendo backend FastAPI de ACE-Step...")

backend_code = '''#!/usr/bin/env python3
"""
ACE-Step Backend - FastAPI
Servidor de generación musical con ACE-Step para el proyecto Documusic
"""
import os
import uuid
import asyncio
import threading
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Documusic ACE-Step Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ACESTEP_DIR = "/home/pepe/acestep"
OUTPUT_DIR = "/home/pepe/documusic-outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Estado de los trabajos en memoria
jobs = {}


def run_acestep(job_id: str, prompt: str, lyrics: str, duration: float = 30.0):
    """Ejecuta ACE-Step en background usando su API de Python."""
    try:
        jobs[job_id]["status"] = "generating"
        jobs[job_id]["logs"].append("🎵 Iniciando ACE-Step...")

        output_path = os.path.join(OUTPUT_DIR, f"{job_id}.wav")

        # Construir script inline para ACE-Step
        infer_script = f"""
import sys
sys.path.insert(0, "{ACESTEP_DIR}")

import torch
print(f"CUDA disponible: {{torch.cuda.is_available()}}", flush=True)
if torch.cuda.is_available():
    print(f"GPU: {{torch.cuda.get_device_name(0)}}", flush=True)
    print(f"VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}} GB", flush=True)

from acestep.pipeline import ACEStepPipeline

print("Cargando modelo ACE-Step...", flush=True)
pipeline = ACEStepPipeline(
    checkpoint_dir="{ACESTEP_DIR}",
    device="cuda" if torch.cuda.is_available() else "cpu",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
)

print("Generando música...", flush=True)
result = pipeline(
    prompt="{prompt.replace(chr(34), chr(39))}",
    lyrics="{lyrics.replace(chr(34), chr(39))}",
    duration={duration},
    num_inference_steps=60,
    guidance_scale=7.0,
)

print(f"Guardando en {output_path}...", flush=True)
import soundfile as sf
import numpy as np
audio = result["audio"]
if isinstance(audio, torch.Tensor):
    audio = audio.cpu().numpy()
sf.write("{output_path}", audio.T if audio.ndim == 2 else audio, 44100)
print("GENERATION_COMPLETE", flush=True)
"""
        # Guardar script temporal
        script_path = f"/tmp/run_acestep_{job_id}.py"
        with open(script_path, 'w') as f:
            f.write(infer_script)

        # Configurar entorno con GPU
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"
        env["PYTHONPATH"] = ACESTEP_DIR
        python_path = os.path.join(ACESTEP_DIR, "venv", "bin", "python3")
        if not os.path.exists(python_path):
            python_path = "python3"

        jobs[job_id]["logs"].append("🚀 Lanzando inferencia en GPU RTX 5080...")

        process = subprocess.Popen(
            [python_path, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
        )

        # Capturar logs en tiempo real
        def capture():
            for line in process.stdout:
                clean = line.strip()
                if clean:
                    print(f"[ACE-Step][{job_id}] {clean}", flush=True)
                    jobs[job_id]["logs"].append(clean)
                    if len(jobs[job_id]["logs"]) > 200:
                        jobs[job_id]["logs"].pop(0)
            process.wait()
            if process.returncode == 0 and os.path.exists(output_path):
                jobs[job_id]["status"] = "done"
                jobs[job_id]["audio_url"] = f"/outputs/{job_id}.wav"
                jobs[job_id]["logs"].append("✅ ¡Música generada con éxito!")
                print(f"[ACE-Step] ✅ Job {job_id} completado.")
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["logs"].append(f"❌ Error (código {process.returncode})")
                print(f"[ACE-Step] ❌ Job {job_id} falló.")
            # Limpiar script temporal
            try:
                os.remove(script_path)
            except:
                pass

        t = threading.Thread(target=capture, daemon=True)
        t.start()

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["logs"].append(f"❌ Excepción: {str(e)}")
        print(f"[ACE-Step] ❌ Excepción en job {job_id}: {e}")


@app.get("/")
@app.get("/api")
async def root():
    return {"status": "ok", "engine": "ACE-Step", "version": "1.0"}


@app.post("/api/generate")
async def generate(data: dict, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    prompt = data.get("prompt", "upbeat pop song")
    lyrics = data.get("lyrics", "")
    duration = float(data.get("duration", 30.0))

    jobs[job_id] = {
        "status": "pending",
        "logs": [f"📋 Trabajo {job_id} registrado", "⏳ Iniciando motor ACE-Step..."],
        "audio_url": None,
    }

    background_tasks.add_task(run_acestep, job_id, prompt, lyrics, duration)

    return JSONResponse({
        "job_id": job_id,
        "model_status": "generating",
        "message": "Generación iniciada con ACE-Step",
    })


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        return JSONResponse({"error": "Job no encontrado"}, status_code=404)
    return JSONResponse(jobs[job_id])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
'''

    # Subir el backend via SFTP
    sftp = client.open_sftp()
    with sftp.open("/home/pepe/documusic/backend/main_acestep.py", "w") as f:
        f.write(backend_code)
    sftp.close()
    print("      ✅ Backend subido a /home/pepe/documusic/backend/main_acestep.py")

# ─────────────────────────────────────────────────────
# RESUMEN FINAL
# ─────────────────────────────────────────────────────
print("\n" + "="*60)
print("✅ DESPLIEGUE ACE-Step COMPLETADO")
print("="*60)
print("""
📋 PRÓXIMOS PASOS EN EL SERVIDOR (Pop!_OS):

1. Activar el nuevo backend:
   cd ~/documusic
   source /home/pepe/acestep/venv/bin/activate
   uvicorn backend.main_acestep:app --host 0.0.0.0 --port 8000 &

2. O si prefieres con Docker (más limpio):
   docker stop documusic_backend
   cd ~/documusic
   docker run -d --name documusic_acestep \\
     --gpus all \\
     -p 8000:8000 \\
     -v /home/pepe/acestep:/acestep \\
     -v /home/pepe/documusic-outputs:/outputs \\
     pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime \\
     bash -c "cd /acestep && pip install -e . -q && uvicorn backend.main_acestep:app --host 0.0.0.0 --port 8000"

3. Verificar que funciona:
   curl http://localhost:8000/api

4. Generar desde el frontend (ya funciona igual que antes)
""")

client.close()
print("🔌 Conexión SSH cerrada.")
