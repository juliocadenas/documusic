import os
import glob
import re
import uuid
import random
import subprocess
import logging
import torch
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx

# DocuMusic modules
from prompt_enricher import enrich_style_prompt, get_enrichment_preview
from gpu_watchdog import start_watchdog, get_watchdog_status, can_generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

app.mount("/api/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

def _download_file(url: str, dest: str, min_size: int = 100) -> bool:
    """Descarga un archivo desde URL. Retorna True si tuvo éxito y el archivo > min_size bytes."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-o", dest, url],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) >= min_size:
            return True
        return False
    except Exception:
        return False


def _ensure_models_available():
    """
    Garantiza que el paquete 'models' sea importable.
    Descarga xcodec_mini_infer desde Hugging Face (repo público m-a-p/xcodec_mini_infer).
    Funciona en caliente — no requiere rebuild de Docker.
    """
    xcodec_in_inference = f"{YUE_DIR}/inference/xcodec_mini_infer"

    # 1. Verificar si models/ ya existe y tiene contenido real
    models_dir = f"{xcodec_in_inference}/models"
    critical_file = f"{models_dir}/soundstream_hubert_new.py"
    if os.path.exists(critical_file) and os.path.getsize(critical_file) > 100:
        logger.info(f"[Startup] ✅ models/ ya existe con contenido real en {models_dir}")
        return

    # 2. Descargar desde Hugging Face
    logger.info(f"[Startup] ⚠️ models/ no encontrado o vacío, descargando desde Hugging Face...")

    os.makedirs(models_dir, exist_ok=True)

    # Hugging Face resolve URLs para el repo m-a-p/xcodec_mini_infer
    hf_base = "https://huggingface.co/m-a-p/xcodec_mini_infer/resolve/main"

    # GitHub raw URLs como fallback (desde el fork/commit del submódulo)
    gh_base = "https://raw.githubusercontent.com/multimodal-art-projection/xcodec_mini_infer/main"

    files_to_download = [
        "models/__init__.py",
        "models/soundstream_hubert_new.py",
        "models/encodec.py",
        "models/vencodec.py",
        "models/vencodec_utils.py",
    ]

    success_count = 0
    for rel_path in files_to_download:
        dest = f"{xcodec_in_inference}/{rel_path}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        # Intentar Hugging Face primero, luego GitHub
        urls = [
            f"{hf_base}/{rel_path}",
            f"{gh_base}/{rel_path}",
        ]

        downloaded = False
        for url in urls:
            logger.info(f"[Startup] Intentando {url}...")
            if _download_file(url, dest, min_size=50):
                success_count += 1
                logger.info(f"[Startup] ✅ {rel_path} descargado ({os.path.getsize(dest)} bytes) desde {url}")
                downloaded = True
                break

        if not downloaded:
            logger.warning(f"[Startup] ⚠️ No se pudo descargar {rel_path} desde ninguna fuente")

    # 3. Verificar resultado
    if os.path.exists(critical_file) and os.path.getsize(critical_file) > 100:
        logger.info(f"[Startup] ✅ soundstream_hubert_new.py OK ({os.path.getsize(critical_file)} bytes)")
        logger.info(f"[Startup] ✅ models/ contiene: {os.listdir(models_dir)}")
    else:
        logger.error(f"[Startup] ❌ Falló la descarga de models/")
        # Último recurso: intentar git clone con la URL de Hugging Face
        logger.info(f"[Startup] 🔄 Último intento: git clone desde Hugging Face...")
        try:
            import shutil
            shutil.rmtree(xcodec_in_inference, ignore_errors=True)
            result = subprocess.run(
                ["git", "clone", "https://huggingface.co/m-a-p/xcodec_mini_infer", xcodec_in_inference],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                logger.info(f"[Startup] ✅ Clone desde Hugging Face exitoso")
                logger.info(f"[Startup] Contenido: {os.listdir(xcodec_in_inference)}")
            else:
                logger.error(f"[Startup] ❌ Clone falló: {result.stderr[:300]}")
        except Exception as e:
            logger.error(f"[Startup] ❌ Último intento falló: {e}")


# 🐕 Start GPU Watchdog on startup
@app.on_event("startup")
async def startup_event():
    start_watchdog()
    _ensure_models_available()
    logger.info("[Startup] 🐕 GPU Watchdog iniciado — monitoreando VRAM y temperatura")

jobs = {}

# Tags que YuE entiende como secciones válidas
VALID_SECTION_TAGS = {'verse', 'chorus', 'bridge', 'intro', 'outro'}

# ============================================================
# FASE 0.1: Parámetros de inferencia optimizados
# ============================================================
YUE_PARAMS = {
    "max_new_tokens": 4096,       # Más tokens = canción más larga (60s → 90s+)
    "run_n_segments": 3,          # 3 segmentos para mejor estructura verso/coro/bridge
    "repetition_penalty": 1.1,    # Evitar loops (ya es default en YuE, explícito para claridad)
    "stage2_batch_size": 4,       # Batch size para Stage 2 (default)
    "rescale": True,              # Evitar clipping en la salida
}

# FASE 0.3: Configuración de multi-variante
VARIANT_CONFIG = {
    "enabled": True,              # Generar múltiples variantes
    "count": 2,                   # Número de variantes (2 para no saturar GPU)
    "seeds": "random",            # "random" o lista de ints
}


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


def find_xcodec_paths():
    """Busca las rutas de xcodec_mini_infer de forma robusta."""
    search_bases = [
        "/opt/YuE",
        "/opt/YuE/inference",
        "/app/models",
    ]
    for base in search_bases:
        config_files = glob.glob(f"{base}/**/final_ckpt/config.yaml", recursive=True)
        ckpt_files = glob.glob(f"{base}/**/final_ckpt/ckpt_*.pth", recursive=True)

        if config_files and ckpt_files:
            return config_files[0], ckpt_files[0]

    return None, None


def sanitize_lyrics(lyrics: str) -> str:
    """
    Limpia la letra para que YuE la entienda correctamente.
    - Elimina tags de estilo como [Genre: ...], [Vocal: ...], etc.
    - Conserva solo secciones válidas: [verse], [chorus], [bridge], [intro], [outro]
    - Garantiza que siempre haya al menos 2 secciones
    """
    formatted = lyrics.strip()

    # 1. Eliminar tags no estándar (cualquier [xxx] que NO sea una sección válida)
    formatted = re.sub(
        r'\[(?!verse\b|chorus\b|bridge\b|intro\b|outro\b)[^\]]+\]',
        '',
        formatted,
        flags=re.IGNORECASE
    ).strip()

    # 2. Limpiar líneas vacías excesivas (máximo 2 saltos consecutivos)
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    # 3. Verificar si quedaron secciones válidas
    has_sections = any(
        f'[{tag}]' in formatted.lower()
        for tag in VALID_SECTION_TAGS
    )

    if not has_sections:
        lines = [l.strip() for l in formatted.split('\n') if l.strip()]
        if not lines:
            lines = ["Docuplay music", "Our platform for learning"]
        mid = max(1, len(lines) // 2)
        verse_lines = lines[:mid]
        chorus_lines = lines[mid:] if len(lines) > mid else lines[:mid]
        formatted = (
            '[verse]\n' + '\n'.join(verse_lines) + '\n\n' +
            '[chorus]\n' + '\n'.join(chorus_lines) + '\n\n'
        )
        if len(lines) > mid * 2:
            formatted += '[verse]\n' + '\n'.join(lines[mid * 2:]) + '\n\n'

    return formatted.strip()


def extract_style_from_lyrics(lyrics: str) -> str:
    """
    Extrae metadata de estilo embebida en la letra como tags [Genre: ...], [Mood: ...], etc.
    Retorna un style_prompt limpio combinando los tags encontrados.
    """
    style_tags = {
        'genre': re.search(r'\[Genre:\s*([^\]]+)\]', lyrics, re.IGNORECASE),
        'vocal': re.search(r'\[Vocal:\s*([^\]]+)\]', lyrics, re.IGNORECASE),
        'mood': re.search(r'\[Mood:\s*([^\]]+)\]', lyrics, re.IGNORECASE),
        'instrumentation': re.search(r'\[Instrumentation:\s*([^\]]+)\]', lyrics, re.IGNORECASE),
        'tempo': re.search(r'\[Tempo:\s*([^\]]+)\]', lyrics, re.IGNORECASE),
    }

    parts = []
    for key, match in style_tags.items():
        if match:
            parts.append(match.group(1).strip())

    return ', '.join(parts) if parts else ''


@app.get("/")
@app.get("/api")
def status():
    gpu_ok = torch.cuda.is_available()
    yue_script = find_yue_script()
    xcodec_config, xcodec_ckpt = find_xcodec_paths()

    yue_files = []
    if os.path.exists(YUE_DIR):
        yue_files = os.listdir(YUE_DIR)

    model_files = []
    if os.path.exists(MODELS_DIR):
        model_files = os.listdir(MODELS_DIR)

    diagnostics = {
        "yue_dir_exists": os.path.exists(YUE_DIR),
        "yue_inference_dir_exists": os.path.exists(f"{YUE_DIR}/inference"),
        "stage1_exists": os.path.exists(f"{MODELS_DIR}/YuE-s1"),
        "stage2_exists": os.path.exists(f"{MODELS_DIR}/YuE-s2"),
        "xcodec_config_found": xcodec_config is not None,
        "xcodec_ckpt_found": xcodec_ckpt is not None,
        "xcodec_config_path": xcodec_config,
        "xcodec_ckpt_path": xcodec_ckpt,
    }

    return {
        "status": "Online",
        "gpu": torch.cuda.get_device_name(0) if gpu_ok else "RTX 5080",
        "vram_free": f"{torch.cuda.mem_get_info()[0] // 1024 ** 2} MB" if gpu_ok else "16 GB",
        "yue_ready": os.path.exists(f"{MODELS_DIR}/YuE-s1"),
        "yue_script": yue_script,
        "yue_files": yue_files[:20],
        "model_files": model_files,
        "diagnostics": diagnostics,
        "variant_config": VARIANT_CONFIG,
        "yue_params": YUE_PARAMS,
    }


@app.get("/api/diagnose")
def diagnose_yue():
    """Diagnóstico completo de la instalación de YuE en el contenedor."""
    # Contenido detallado de xcodec_mini_infer dentro de inference/
    xcodec_in_inference = f"{YUE_DIR}/inference/xcodec_mini_infer"
    xcodec_deep = {}
    if os.path.isdir(xcodec_in_inference):
        xcodec_deep["contents"] = os.listdir(xcodec_in_inference)
        models_in_xcodec = f"{xcodec_in_inference}/models"
        if os.path.isdir(models_in_xcodec):
            xcodec_deep["models_contents"] = os.listdir(models_in_xcodec)
        else:
            xcodec_deep["models_contents"] = "NO EXISTE"
            # Check if it's an empty submodule
            xcodec_deep["is_empty_submodule"] = len(os.listdir(xcodec_in_inference)) <= 1 and '.git' in os.listdir(xcodec_in_inference)
    else:
        xcodec_deep["contents"] = "NO EXISTE"

    result = {
        "yue_dir": {"path": YUE_DIR, "exists": os.path.isdir(YUE_DIR)},
        "yue_contents": os.listdir(YUE_DIR) if os.path.isdir(YUE_DIR) else [],
        "models_at_root": {
            "exists": os.path.isdir(f"{YUE_DIR}/models"),
            "is_symlink": os.path.islink(f"{YUE_DIR}/models"),
            "target": os.readlink(f"{YUE_DIR}/models") if os.path.islink(f"{YUE_DIR}/models") else None,
        },
        "xcodec_at_root": {
            "exists": os.path.isdir(f"{YUE_DIR}/xcodec_mini_infer"),
            "contents": os.listdir(f"{YUE_DIR}/xcodec_mini_infer") if os.path.isdir(f"{YUE_DIR}/xcodec_mini_infer") else [],
        },
        "xcodec_in_inference": xcodec_deep,
        "inference_dir": {
            "exists": os.path.isdir(f"{YUE_DIR}/inference"),
            "contents": os.listdir(f"{YUE_DIR}/inference") if os.path.isdir(f"{YUE_DIR}/inference") else [],
        },
        "all_models_dirs": glob.glob(f"{YUE_DIR}/**/models", recursive=True),
        "infer_script": find_yue_script(),
    }
    # Test de importación con múltiples rutas
    try:
        import sys
        test_paths = [YUE_DIR, f"{YUE_DIR}/xcodec_mini_infer", xcodec_in_inference]
        for p in test_paths:
            if p not in sys.path and os.path.isdir(p):
                sys.path.insert(0, p)
        from models.soundstream_hubert_new import SoundStream
        result["import_test"] = "✅ SUCCESS"
    except ImportError as e:
        result["import_test"] = f"❌ FAILED: {e}"
        result["sys_path"] = [p for p in sys.path if 'YuE' in p or 'models' in p]
    return result


@app.post("/api/generate")
async def generate(req: dict, background_tasks: BackgroundTasks):
    lyrics = req.get("lyrics", "")
    style_prompt = req.get("style_prompt", "")
    num_variants = req.get("num_variants", VARIANT_CONFIG["count"])
    job_id = str(uuid.uuid4())[:8]

    # 🐕 Watchdog check: can GPU handle a new generation?
    gpu_ok, gpu_reason = can_generate()
    if not gpu_ok:
        return {
            "status": "error",
            "message": f"🐕 Watchdog: {gpu_reason}",
            "model_status": "gpu_busy",
            "gpu_status": get_watchdog_status(),
        }

    # Clamp variants to 1-3
    num_variants = max(1, min(3, int(num_variants)))

    stage1_path = f"{MODELS_DIR}/YuE-s1"
    stage2_path = f"{MODELS_DIR}/YuE-s2"
    yue_script = find_yue_script()

    # Si no hay modelos o el script no se encuentra, usar audio demo
    if not os.path.exists(stage1_path) or yue_script is None:
        reason = "Modelos no encontrados"
        if not os.path.exists(stage1_path):
            reason = f"Stage1 no encontrado en {stage1_path}"
        elif not os.path.exists(stage2_path):
            reason = f"Stage2 no encontrado en {stage2_path}"
        elif yue_script is None:
            reason = f"Script YuE no localizado en {YUE_DIR}"
        return {
            "status": "success",
            "generated_lyrics": lyrics,
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
            "message": f"⚠️ {reason}. Usando audio demo.",
            "model_status": "demo"
        }

    # Extraer estilo embebido en la letra si no hay style_prompt explícito
    embedded_style = extract_style_from_lyrics(lyrics)
    if embedded_style and not style_prompt:
        style_prompt = embedded_style
    elif embedded_style and style_prompt:
        style_prompt = f"{style_prompt}, {embedded_style}"

    # Fallback de estilo si sigue vacío
    if not style_prompt.strip():
        style_prompt = "pop rock, melodic male vocal, energetic"

    # 🎨 PROMPT ENRICHMENT: Transform short prompts into rich descriptions
    # "American Country" → "American Country, warm male baritone, fiddle, pedal steel, Nashville..."
    original_prompt = style_prompt
    style_prompt = enrich_style_prompt(style_prompt)
    logger.info(f"[Generate] Prompt enriquecido: '{original_prompt}' → '{style_prompt}'")

    # Sanitizar la letra (eliminar tags de estilo, conservar solo secciones válidas)
    clean_lyrics = sanitize_lyrics(lyrics)

    logger.info(f"[Generate] Job {job_id} | Style: '{style_prompt}' | Variants: {num_variants} | Lyrics sections: {clean_lyrics.count('[')} tags")

    # Generate seeds for each variant
    seeds = []
    for i in range(num_variants):
        if VARIANT_CONFIG["seeds"] == "random":
            seeds.append(random.randint(1, 999999))
        else:
            seeds.append(42 + i)

    # Initialize job with variant tracking
    jobs[job_id] = {
        "status": "generating",
        "audio_url": None,
        "logs": [],
        "variants": [],           # List of variant results
        "num_variants": num_variants,
        "completed_variants": 0,
        "seeds": seeds,
    }

    jobs[job_id]["logs"] = [
        f"🎯 Generando {num_variants} variante(s) con seeds: {seeds}",
        f"Style: {style_prompt}",
    ]

    background_tasks.add_task(
        run_yue_inference_multi,
        job_id, clean_lyrics, style_prompt, yue_script, seeds
    )

    return {
        "status": "success",
        "job_id": job_id,
        "generated_lyrics": clean_lyrics,
        "audio_url": None,
        "message": f"🎵 Generando {num_variants} variante(s) con YuE en la RTX 5080...",
        "model_status": "generating",
        "num_variants": num_variants,
        "seeds": seeds,
    }


def _build_inference_cmd(tmp_dir: str, output_path: str, yue_script: str, seed: int) -> list:
    """Build the YuE inference command with optimized parameters (Fase 0.1)."""
    yue_inference_dir = os.path.dirname(yue_script) if "inference" in yue_script else "/opt/YuE/inference"

    # Determinar el CWD y la ruta relativa del script.
    # Usar /opt/YuE como CWD para que Python encuentre el paquete 'models/'
    # que está en /opt/YuE/models/ (no en /opt/YuE/inference/models/).
    yue_root = "/opt/YuE"
    if os.path.isdir(yue_root):
        # Ruta relativa del script desde la raíz de YuE
        script_rel = os.path.relpath(yue_script, yue_root)  # e.g. "inference/infer.py"
        cwd = yue_root
    else:
        script_rel = "infer.py"
        cwd = yue_inference_dir

    cmd = [
        "python3", script_rel,
        "--stage1_model", f"{MODELS_DIR}/YuE-s1",
        "--stage2_model", f"{MODELS_DIR}/YuE-s2",
        "--genre_txt", f"{tmp_dir}/style.txt",
        "--lyrics_txt", f"{tmp_dir}/lyrics.txt",
        "--output_dir", output_path,
        "--cuda_idx", "0",
        # FASE 0.1: Parámetros optimizados
        "--max_new_tokens", str(YUE_PARAMS["max_new_tokens"]),
        "--run_n_segments", str(YUE_PARAMS["run_n_segments"]),
        "--repetition_penalty", str(YUE_PARAMS["repetition_penalty"]),
        "--stage2_batch_size", str(YUE_PARAMS["stage2_batch_size"]),
        "--seed", str(seed),
    ]

    # Add rescale flag if enabled
    if YUE_PARAMS.get("rescale", True):
        cmd.append("--rescale")

    # Buscar rutas de xcodec de forma robusta
    xcodec_config, xcodec_ckpt = find_xcodec_paths()

    if xcodec_config and xcodec_ckpt:
        cmd.extend(["--basic_model_config", xcodec_config])
        cmd.extend(["--resume_path", xcodec_ckpt])
    else:
        default_config = f"{yue_inference_dir}/xcodec_mini_infer/final_ckpt/config.yaml"
        default_ckpt = f"{yue_inference_dir}/xcodec_mini_infer/final_ckpt/ckpt_00360000.pth"
        if os.path.exists(default_config) and os.path.exists(default_ckpt):
            cmd.extend(["--basic_model_config", default_config])
            cmd.extend(["--resume_path", default_ckpt])

    return cmd, cwd


def _get_env(yue_inference_dir: str) -> dict:
    """Get environment variables for YuE inference."""
    env = os.environ.copy()
    paths = [
        yue_inference_dir,
        f"{yue_inference_dir}/xcodec_mini_infer",
        f"{yue_inference_dir}/xcodec_mini_infer/models",
        f"{yue_inference_dir}/vocos",
        "/opt/YuE",
        "/opt/YuE/inference",
        "/opt/YuE/xcodec_mini_infer",
        "/opt/YuE/xcodec_mini_infer/models",
        "/opt/YuE/inference/xcodec_mini_infer",          # ubicación real tras git clone
        "/opt/YuE/inference/xcodec_mini_infer/models",   # models/ vive aquí
    ]
    existing_paths = [p for p in paths if os.path.exists(p)]

    # Buscar dinámicamente todos los directorios 'models' bajo /opt/YuE
    # y añadir sus padres al PYTHONPATH para que `from models.xxx` funcione
    models_dirs = glob.glob("/opt/YuE/**/models", recursive=True)
    for md in models_dirs:
        parent = os.path.dirname(md)
        if os.path.isdir(md) and parent not in existing_paths:
            existing_paths.append(parent)
            logger.info(f"[PYTHONPATH] Añadido padre de models/: {parent}")

    # Eliminar duplicados manteniendo orden
    seen = set()
    unique_paths = []
    for p in existing_paths:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)

    env["PYTHONPATH"] = ":".join(unique_paths) + ":" + env.get("PYTHONPATH", "")
    env["ATTENTION_IMPLEMENTATION"] = "eager"
    env["USE_FLASH_ATTN"] = "0"
    env["FORCE_FLASH_ATTN"] = "0"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["PYTHONUNBUFFERED"] = "1"
    env["CUDA_LAUNCH_BLOCKING"] = "1"
    logger.info(f"[PYTHONPATH] Rutas finales: {unique_paths}")
    return env


def _find_audio_file(output_path: str) -> str | None:
    """Find the generated audio file (MP3 preferred, WAV fallback)."""
    # Search for MP3 first (YuE with torchcodec generates MP3)
    audio_files = glob.glob(f"{output_path}/**/*.mp3", recursive=True)
    if not audio_files:
        audio_files = glob.glob(f"{output_path}/*.mp3")
    # Fallback to WAV
    if not audio_files:
        audio_files = glob.glob(f"{output_path}/**/*.wav", recursive=True)
    if not audio_files:
        audio_files = glob.glob(f"{output_path}/*.wav")

    # Prefer _mixed files (final mix from YuE)
    mixed_files = [f for f in audio_files if '_mixed' in f]
    if mixed_files:
        audio_files = mixed_files

    return audio_files[0] if audio_files else None


def _finalize_audio(source_path: str, job_id: str, variant_idx: int) -> str:
    """
    Convert/copy audio to final MP3 and apply mastering pipeline (Fase 0.2).
    Returns the path to the mastered MP3.
    """
    from audio_master import master_audio_simple

    if variant_idx == 0:
        # Primary variant: job_id.mp3
        final_raw = f"{OUTPUT_DIR}/{job_id}.mp3"
        final_mastered = f"{OUTPUT_DIR}/{job_id}.mp3"
    else:
        # Additional variants: job_id_v2.mp3, job_id_v3.mp3
        final_raw = f"{OUTPUT_DIR}/{job_id}_v{variant_idx + 1}.mp3"
        final_mastered = f"{OUTPUT_DIR}/{job_id}_v{variant_idx + 1}.mp3"

    # Convert to MP3 if needed
    if source_path.endswith('.mp3'):
        import shutil
        shutil.copy2(source_path, final_raw)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", source_path, "-b:a", "192k", final_raw],
            check=True, capture_output=True
        )

    # FASE 0.2: Apply mastering pipeline
    try:
        mastered_path = master_audio_simple(final_raw, final_mastered)
        logger.info(f"[Master] ✅ Variant {variant_idx + 1} mastered: {mastered_path}")
        return mastered_path
    except Exception as e:
        logger.warning(f"[Master] Mastering failed for variant {variant_idx + 1}: {e}")
        return final_raw


def run_yue_inference_multi(job_id: str, lyrics: str, style_prompt: str, yue_script: str, seeds: list):
    """
    FASE 0.3: Multi-variant generation.
    Generates multiple variants with different seeds, applies mastering to each.
    """
    try:
        import threading

        tmp_dir = f"/app/tmp/{job_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        with open(f"{tmp_dir}/lyrics.txt", "w", encoding="utf-8") as f:
            f.write(lyrics.strip())
        with open(f"{tmp_dir}/style.txt", "w", encoding="utf-8") as f:
            f.write(style_prompt)

        num_variants = len(seeds)
        variant_results = []

        for variant_idx, seed in enumerate(seeds):
            variant_label = f"V{variant_idx + 1}/{num_variants}"
            jobs[job_id]["logs"].append(f"🎵 Iniciando variante {variant_label} (seed={seed})...")

            # Each variant gets its own output subdirectory
            variant_output = f"{OUTPUT_DIR}/{job_id}/v{variant_idx + 1}"
            os.makedirs(variant_output, exist_ok=True)

            # Build command with optimized parameters
            cmd, yue_inference_dir = _build_inference_cmd(tmp_dir, variant_output, yue_script, seed)
            env = _get_env(yue_inference_dir)

            logger.info(f"[YuE] 🚀 Variant {variant_label} | Seed: {seed} | CMD: {' '.join(cmd)}")

            # Run inference synchronously (one variant at a time to manage VRAM)
            error_lines = []
            try:
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

                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        prefix = f"[{variant_label}]"
                        print(f"[{job_id}] {prefix} {clean_line}")
                        jobs[job_id]["logs"].append(f"{prefix} {clean_line}")
                        if any(kw in clean_line.lower() for kw in ['error', 'traceback', 'exception', 'failed']):
                            error_lines.append(clean_line)

                process.wait()

                if process.returncode == 0:
                    # Find the generated audio
                    source_path = _find_audio_file(variant_output)
                    if source_path:
                        # FASE 0.2: Apply mastering pipeline
                        jobs[job_id]["logs"].append(f"🎚️ Masterizando variante {variant_label}...")
                        final_path = _finalize_audio(source_path, job_id, variant_idx)

                        # Determine the URL
                        if variant_idx == 0:
                            audio_url = f"/outputs/{job_id}.mp3"
                        else:
                            audio_url = f"/outputs/{job_id}_v{variant_idx + 1}.mp3"

                        # Get metrics
                        from audio_master import get_audio_metrics
                        metrics = get_audio_metrics(final_path)

                        variant_results.append({
                            "index": variant_idx,
                            "seed": seed,
                            "audio_url": audio_url,
                            "duration": metrics.get("duration_seconds", 0),
                            "file_size": metrics.get("file_size_bytes", 0),
                            "lufs": metrics.get("lufs", 0),
                        })

                        jobs[job_id]["logs"].append(
                            f"✅ Variante {variant_label} lista: {metrics.get('duration_seconds', 0):.1f}s, "
                            f"LUFS: {metrics.get('lufs', 0):.1f}"
                        )
                    else:
                        all_files = glob.glob(f"{variant_output}/**/*", recursive=True)
                        jobs[job_id]["logs"].append(
                            f"⚠️ Variante {variant_label}: No se encontró audio. "
                            f"Archivos: {[os.path.basename(f) for f in all_files[:5]]}"
                        )
                        variant_results.append({
                            "index": variant_idx,
                            "seed": seed,
                            "audio_url": None,
                            "error": "No audio file found",
                        })
                else:
                    error_detail = "\n".join(error_lines[-5:]) if error_lines else "Unknown error"
                    jobs[job_id]["logs"].append(f"❌ Variante {variant_label} falló (code {process.returncode})")
                    variant_results.append({
                        "index": variant_idx,
                        "seed": seed,
                        "audio_url": None,
                        "error": f"Process failed with code {process.returncode}: {error_detail}",
                    })

            except Exception as e:
                jobs[job_id]["logs"].append(f"❌ Variante {variant_label} excepción: {e}")
                variant_results.append({
                    "index": variant_idx,
                    "seed": seed,
                    "audio_url": None,
                    "error": str(e),
                })

            jobs[job_id]["completed_variants"] = variant_idx + 1

        # All variants complete - select the best one
        successful_variants = [v for v in variant_results if v.get("audio_url")]
        jobs[job_id]["variants"] = variant_results

        if successful_variants:
            # Select best variant: prefer longer duration, then closer to -14 LUFS
            best = max(
                successful_variants,
                key=lambda v: (
                    v.get("duration", 0),
                    -abs(v.get("lufs", 0) - (-14)),  # Closer to -14 is better
                )
            )

            # The primary URL is always the best variant
            # If best is not v1, we need to copy it as the primary
            if best["index"] != 0 and best.get("audio_url"):
                import shutil
                best_source = f"{OUTPUT_DIR}/{job_id}_v{best['index'] + 1}.mp3"
                best_dest = f"{OUTPUT_DIR}/{job_id}.mp3"
                if os.path.exists(best_source):
                    shutil.copy2(best_source, best_dest)
                    # Update variant 0 to point to the copied file
                    variant_results[0] = {
                        "index": 0,
                        "seed": seeds[0],
                        "audio_url": f"/outputs/{job_id}.mp3",
                        "duration": best.get("duration", 0),
                        "file_size": best.get("file_size", 0),
                        "lufs": best.get("lufs", 0),
                        "is_best_copy": True,
                    }

            primary_url = f"/outputs/{job_id}.mp3"
            jobs[job_id].update({
                "status": "done",
                "audio_url": primary_url,
                "best_variant": best["index"],
            })
            jobs[job_id]["logs"].append(
                f"🏆 Mejor variante: V{best['index'] + 1} "
                f"(duración: {best.get('duration', 0):.1f}s, LUFS: {best.get('lufs', 0):.1f})"
            )
            jobs[job_id]["logs"].append("✅ Todas las variantes completadas.")
        else:
            jobs[job_id].update({
                "status": "error",
                "error": "Todas las variantes fallaron.",
                "error_detail": "\n".join(
                    v.get("error", "Unknown") for v in variant_results
                ),
            })

    except Exception as e:
        logger.error(f"[YuE] ❌ Error crítico en multi-variant: {e}", exc_info=True)
        jobs[job_id].update({"status": "error", "error": str(e)})


# Keep backward compatibility: single variant endpoint
def run_yue_inference(job_id: str, lyrics: str, style_prompt: str, yue_script: str):
    """Legacy single-variant inference (calls multi-variant with count=1)."""
    run_yue_inference_multi(job_id, lyrics, style_prompt, yue_script, seeds=[42])


@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})


@app.get("/api/gpu")
def gpu_status():
    """🐕 GPU Watchdog status endpoint — polled by frontend every 5s."""
    return get_watchdog_status()


@app.post("/api/enrich-preview")
def enrich_preview(req: dict):
    """Preview what the prompt enricher would produce for a given style."""
    style = req.get("style_prompt", "")
    return get_enrichment_preview(style)


@app.get("/api/diagnostics")
def diagnostics():
    """Endpoint de diagnóstico para verificar todas las rutas y dependencias."""
    yue_script = find_yue_script()
    xcodec_config, xcodec_ckpt = find_xcodec_paths()

    checks = {
        "yue_dir": {"path": YUE_DIR, "exists": os.path.exists(YUE_DIR)},
        "yue_inference": {"path": f"{YUE_DIR}/inference", "exists": os.path.exists(f"{YUE_DIR}/inference")},
        "yue_script": {"path": yue_script, "exists": yue_script is not None},
        "stage1_model": {"path": f"{MODELS_DIR}/YuE-s1", "exists": os.path.exists(f"{MODELS_DIR}/YuE-s1")},
        "stage2_model": {"path": f"{MODELS_DIR}/YuE-s2", "exists": os.path.exists(f"{MODELS_DIR}/YuE-s2")},
        "xcodec_config": {"path": xcodec_config, "exists": xcodec_config is not None},
        "xcodec_ckpt": {"path": xcodec_ckpt, "exists": xcodec_ckpt is not None},
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "ffmpeg": {"exists": subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0},
    }

    if os.path.exists(MODELS_DIR):
        checks["model_dir_contents"] = os.listdir(MODELS_DIR)

    inf_dir = f"{YUE_DIR}/inference"
    if os.path.exists(inf_dir):
        checks["yue_inference_contents"] = os.listdir(inf_dir)[:30]

    all_ok = all(
        v.get("exists", v) if isinstance(v, dict) else v
        for v in checks.values()
        if isinstance(v, dict) and "exists" in v
    )

    return {
        "status": "all_ok" if all_ok else "issues_found",
        "checks": checks,
        "yue_params": YUE_PARAMS,
        "variant_config": VARIANT_CONFIG,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
