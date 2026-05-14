import os
import glob
import re
import json
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
from prompt_enricher import enrich_style_prompt, get_enrichment_preview, get_lyrics_enrichment
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
ACESTEP_DIR = "/opt/ACE-Step"
ACESTEP_MODEL_ID = "ACE-Step/ACE-Step-v1-3.5B"
ACESTEP_MODEL_DIR = f"{MODELS_DIR}/ACE-Step-v1-3.5B"
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


def _patch_infer_py():
    """Parcha infer.py: flash_attention_2 → eager, torchaudio.save → soundfile fallback."""
    infer_py = f"{YUE_DIR}/inference/infer.py"
    if not os.path.exists(infer_py):
        logger.warning("[Startup] infer.py no encontrado para parchar")
        return
    try:
        with open(infer_py, 'r') as f:
            content = f.read()
        original = content
        patched = False

        # 1. Reemplazar flash_attention_2 → eager
        if 'flash_attention_2' in content:
            content = content.replace('flash_attention_2', 'eager')
            patched = True
            logger.info("[Startup] infer.py: flash_attention_2 → eager")

        # 2. Parchar from_pretrained() con 8-bit quantization (PCIe estable en RTX 5080)
        import re
        if 'yue_8bit_stable_v1_applied' not in content:
            # Find all AutoModelForCausalLM.from_pretrained(...) calls
            fp_pattern = re.compile(r'AutoModelForCausalLM\.from_pretrained\(')
            matches = list(fp_pattern.finditer(content))
            # Process in reverse order to preserve offsets
            for m in reversed(matches):
                start = m.start()
                # Find matching closing paren
                depth = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == '(':
                        depth += 1
                    elif content[i] == ')':
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                call_block = content[start:end+1]
                # Extract the first argument (model path variable, e.g. stage1_model)
                first_arg_match = re.search(r'from_pretrained\(\s*\n?\s*(\w+)', call_block)
                if not first_arg_match:
                    continue
                model_arg = first_arg_match.group(1)
                # Build clean replacement call WITH 8-bit quantization
                # Required for PCIe stability on RTX 5080 (reduces VRAM ~14GB → ~7GB)
                new_call = (
                    f'AutoModelForCausalLM.from_pretrained(\n'
                    f'    {model_arg},\n'
                    f'    attn_implementation="eager",\n'
                    f'    load_in_8bit=True,\n'
                    f'    device_map="auto",\n'
                    f')'
                )
                content = content[:start] + new_call + content[end+1:]
                patched = True
                logger.info(f"[Startup] infer.py: patched from_pretrained({model_arg}) → 8-bit quantization (stable)")

            # Comment out model.to(device) — incompatible with device_map="auto"
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                stripped = line.lstrip()
                if re.match(r'(model\w*\s*=\s*)?model\w*\.to\(', stripped) and '# [DocuMusic]' not in line:
                    indent = line[:len(line) - len(stripped)]
                    new_lines.append(f'{indent}# {stripped} # [DocuMusic] incompatible with device_map="auto"')
                    patched = True
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)

            content += "\n# yue_8bit_stable_v1_applied = True\n"

        # 3. Parchar torchaudio.save para usar soundfile como fallback (torchcodec no instalado)
        if 'torchaudio_patched_v3' not in content:
            # Remove old patches if present (v1 or v2)
            if 'torchaudio_save_patched' in content or 'torchaudio_patched_v3' not in content:
                old_patch_start = content.find('# === DOCUMUSIC PATCH')
                if old_patch_start != -1:
                    # Find the end of the old patch block
                    old_patch_end = content.find('# torchaudio', old_patch_start)
                    if old_patch_end != -1:
                        old_patch_end = content.find('\n', old_patch_end) + 1
                        content = content[:old_patch_start] + content[old_patch_end:]
                        logger.info("[Startup] infer.py: removed old torchaudio patch")

            torchaudio_import = "import torchaudio"
            if torchaudio_import in content:
                patch_code = """

# === DOCUMUSIC PATCH v3: torchaudio.save + torchaudio.load fallback a soundfile ===
import torchaudio as _ta_orig
_ta_original_save = _ta_orig.save
_ta_original_load = _ta_orig.load
def _safe_ta_save(filepath, src, sample_rate, **kwargs):
    try:
        _ta_original_save(filepath, src, sample_rate, **kwargs)
    except (ImportError, RuntimeError, Exception) as _e:
        import soundfile as sf
        import numpy as np
        wav_np = src.squeeze().cpu().numpy()
        if wav_np.ndim > 1:
            wav_np = wav_np.T
        _fp = str(filepath)
        if not _fp.endswith('.wav'):
            _fp = _fp.rsplit('.', 1)[0] + '.wav'
        sf.write(_fp, wav_np, sample_rate, format='WAV', subtype='PCM_16')
def _safe_ta_load(filepath, **kwargs):
    try:
        return _ta_original_load(filepath, **kwargs)
    except (ImportError, RuntimeError, Exception) as _e:
        import soundfile as sf
        import torch
        import numpy as np
        import os
        _fp = str(filepath)
        if not os.path.exists(_fp) and _fp.endswith('.mp3'):
            _fp = _fp.rsplit('.', 1)[0] + '.wav'
        wav_np, sr = sf.read(_fp)
        if wav_np.ndim == 1:
            wav_np = wav_np.reshape(1, -1)
        else:
            wav_np = wav_np.T
        return torch.tensor(wav_np, dtype=torch.float32), sr
_ta_orig.save = _safe_ta_save
_ta_orig.load = _safe_ta_load
# torchaudio_patched_v3 = True
"""
                idx = content.find(torchaudio_import)
                end_of_line = content.find('\n', idx)
                content = content[:end_of_line + 1] + patch_code + content[end_of_line + 1:]
                patched = True
                logger.info("[Startup] infer.py: ✅ patched torchaudio.save with soundfile fallback v2")

        # 4. Cambiar .mp3 → .wav en rutas de guardado (soundfile solo soporta WAV)
        if 'mp3_to_wav_patched' not in content:
            mp3_replacements = [
                ("+ \".mp3\"", "+ \".wav\""),          # save_path en recons section
                ("'itrack.mp3'", "'itrack.wav'"),      # vocoder stems
                ("'vtrack.mp3'", "'vtrack.wav'"),      # vocoder stems
            ]
            for old, new in mp3_replacements:
                if old in content:
                    content = content.replace(old, new)
                    patched = True
                    logger.info(f"[Startup] infer.py: {old} → {new}")
            # Mark as patched
            content += "\n# mp3_to_wav_patched = True\n"

        # 5. Safe model.cpu() — evitar crash CUDA en cleanup
        if 'safe_cpu_patched' not in content:
            safe_cpu_patch = """
# === DOCUMUSIC PATCH: Safe model.cpu() — evita CUDA crash en cleanup ===
import torch as _torch_safe
_original_module_cpu = _torch_safe.nn.Module.cpu
def _safe_cpu(self):
    try:
        return _original_module_cpu(self)
    except Exception:
        try:
            import gc; gc.collect()
            _torch_safe.cuda.empty_cache()
        except Exception:
            pass
_torch_safe.nn.Module.cpu = _safe_cpu
# safe_cpu_patched = True
"""
            # Insert after the first 'import torch' line
            torch_import_idx = content.find('import torch')
            if torch_import_idx != -1:
                end_of_line = content.find('\n', torch_import_idx)
                content = content[:end_of_line + 1] + safe_cpu_patch + content[end_of_line + 1:]
                patched = True
                logger.info("[Startup] infer.py: ✅ patched safe model.cpu()")

        if patched and content != original:
            with open(infer_py, 'w') as f:
                f.write(content)
            logger.info("[Startup] ✅ infer.py parcheado correctamente")
        else:
            logger.info("[Startup] infer.py: sin cambios necesarios (ya parcheado)")
    except Exception as e:
        logger.warning(f"[Startup] No se pudo parchar infer.py: {e}")


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
    modules_dir = f"{xcodec_in_inference}/modules"

    # Check if everything is already in place
    if (os.path.exists(critical_file) and os.path.getsize(critical_file) > 100
            and os.path.isdir(modules_dir) and os.listdir(modules_dir)):
        logger.info(f"[Startup] ✅ xcodec_mini_infer completo en {xcodec_in_inference}")
        _patch_infer_py()
        return

    # SIEMPRE limpiar __init__.py basura
    init_file = os.path.join(models_dir, "__init__.py")
    if os.path.exists(init_file) and os.path.getsize(init_file) < 100:
        try:
            with open(init_file, 'r') as f:
                content = f.read().strip()
            if '404' in content or 'Not Found' in content or len(content) < 5:
                logger.info(f"[Startup] Limpiando __init__.py basura")
                with open(init_file, 'w') as f:
                    f.write("")
        except Exception:
            with open(init_file, 'w') as f:
                f.write("")

    # Estrategia principal: git clone completo desde Hugging Face
    logger.info(f"[Startup] 🔄 Clonando xcodec_mini_infer completo desde Hugging Face...")
    try:
        import shutil
        shutil.rmtree(xcodec_in_inference, ignore_errors=True)
        result = subprocess.run(
            ["git", "clone", "https://huggingface.co/m-a-p/xcodec_mini_infer", xcodec_in_inference],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            logger.info(f"[Startup] ✅ Clone exitoso. Contenido: {os.listdir(xcodec_in_inference)}")
            if os.path.isdir(models_dir):
                logger.info(f"[Startup] ✅ models/: {os.listdir(models_dir)}")
            if os.path.isdir(modules_dir):
                logger.info(f"[Startup] ✅ modules/: {os.listdir(modules_dir)}")

            # Parchar infer.py para desactivar flash_attention_2
            _patch_infer_py()
            return
        else:
            logger.error(f"[Startup] ❌ Clone falló: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        logger.error("[Startup] ❌ Clone timeout")
    except Exception as e:
        logger.error(f"[Startup] ❌ Clone error: {e}")

    # Fallback: descarga individual de archivos críticos
    logger.info(f"[Startup] ⚠️ Fallback: descarga individual...")
    os.makedirs(models_dir, exist_ok=True)

    # Limpiar archivos < 100 bytes
    for f in os.listdir(models_dir):
        fpath = os.path.join(models_dir, f)
        if os.path.isfile(fpath) and os.path.getsize(fpath) < 100:
            os.remove(fpath)

    hf_base = "https://huggingface.co/m-a-p/xcodec_mini_infer/resolve/main"

    # Descargar todos los archivos Python necesarios
    files_to_download = []
    for subdir in ["models", "modules"]:
        sd = f"{xcodec_in_inference}/{subdir}"
        if os.path.isdir(sd):
            for f in os.listdir(sd):
                if f.endswith('.py') and os.path.getsize(os.path.join(sd, f)) < 50:
                    files_to_download.append(f"{subdir}/{f}")

    # Si no hay archivos que reparar, descargar los conocidos
    if not files_to_download:
        files_to_download = [
            "models/soundstream_hubert_new.py",
            "modules/seanet.py",
        ]

    for rel_path in files_to_download:
        dest = f"{xcodec_in_inference}/{rel_path}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        url = f"{hf_base}/{rel_path}"
        logger.info(f"[Startup] Descargando {rel_path}...")
        if _download_file(url, dest, min_size=50):
            logger.info(f"[Startup] ✅ {rel_path} ({os.path.getsize(dest)} bytes)")
        else:
            logger.warning(f"[Startup] ⚠️ Falló {rel_path}")

    # Asegurar __init__.py en models/ y modules/
    for subdir in ["models", "modules"]:
        init = f"{xcodec_in_inference}/{subdir}/__init__.py"
        if not os.path.exists(init) or os.path.getsize(init) < 5:
            with open(init, 'w') as f:
                f.write("")

    # Verificar resultado
    if os.path.exists(critical_file) and os.path.getsize(critical_file) > 100:
        logger.info(f"[Startup] ✅ soundstream_hubert_new.py OK")
    else:
        logger.error(f"[Startup] ❌ No se pudo completar la descarga de xcodec_mini_infer")


# ============================================================
# ACE-Step 1.5 — Setup (clonar + instalar + descargar modelo)
# ============================================================
def _ensure_acestep_available() -> bool:
    """Ensure ACE-Step repo is cloned, deps installed, and model weights downloaded."""
    ace_available = False

    # 1. Check if ACE-Step source code exists
    if not os.path.exists(f"{ACESTEP_DIR}/acestep"):
        logger.info("[Startup] 🔧 Clonando ACE-Step desde GitHub...")
        try:
            subprocess.run(
                ["git", "clone", "https://github.com/ace-step/ACE-Step.git", ACESTEP_DIR],
                check=True, timeout=180, capture_output=True, text=True
            )
            logger.info("[Startup] ✅ ACE-Step clonado")
        except Exception as e:
            logger.warning(f"[Startup] ⚠️ No se pudo clonar ACE-Step: {e}")
            return False
    else:
        logger.info("[Startup] ✅ ACE-Step repo encontrado")
        ace_available = True

    # 2. Check if ACE-Step is importable (pip install may be needed after container recreate)
    try:
        import acestep  # noqa: F401
        logger.info("[Startup] ✅ ACE-Step importable")
        ace_available = True
    except ImportError:
        logger.info("[Startup] 🔧 Instalando ACE-Step (pip install --no-deps -e .)...")
        try:
            # Use --no-deps to prevent pulling nvidia-nccl-cu12 which breaks PyTorch nightly
            result = subprocess.run(
                ["pip3", "install", "--no-deps", "-e", ACESTEP_DIR],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                logger.info("[Startup] ✅ ACE-Step instalado correctamente (--no-deps)")
                ace_available = True
            else:
                logger.warning(f"[Startup] ⚠️ Error instalando ACE-Step: {result.stderr[-500:]}")
                return False
        except Exception as e:
            logger.warning(f"[Startup] ⚠️ No se pudo instalar ACE-Step: {e}")
            return False

    # 3. Install additional dependencies that ACE-Step might need (with --no-deps for safety)
    try:
        subprocess.run(
            ["pip3", "install", "diffusers", "--no-deps", "--quiet"],
            capture_output=True, text=True, timeout=120
        )
    except Exception:
        pass  # Non-critical

    # 4. Download model weights from HuggingFace if not present
    #    ACE-Step expects subdirs: music_dcae_f8c8, music_vocoder, ace_step_transformer, umt5-base
    ace_model_ready = all(
        os.path.exists(f"{ACESTEP_MODEL_DIR}/{d}")
        for d in ["music_dcae_f8c8", "music_vocoder", "ace_step_transformer", "umt5-base"]
    )
    if ace_available and not ace_model_ready:
        logger.info(f"[Startup] 🔧 Descargando modelo {ACESTEP_MODEL_ID} (~7GB, primera vez)...")
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id=ACESTEP_MODEL_ID,
                local_dir=ACESTEP_MODEL_DIR,
            )
            logger.info("[Startup] ✅ Modelo ACE-Step descargado")
        except Exception as e:
            logger.warning(f"[Startup] ⚠️ No se pudo descargar modelo ACE-Step: {e}")
            # Model will be downloaded on first generation instead (pipeline auto-downloads)

    return ace_available


# 🐕 Start GPU Watchdog on startup
@app.on_event("startup")
async def startup_event():
    # Configurar GPU automáticamente: persistence mode + power limit
    try:
        subprocess.run(["nvidia-smi", "-pm", "1"], capture_output=True, timeout=10)
        result = subprocess.run(["nvidia-smi", "-pl", "250"], capture_output=True, text=True, timeout=10)
        if "was set to 250" in result.stderr or "was set to 250" in result.stdout:
            logger.info("[Startup] ✅ GPU: persistence mode ON, power limit 250W")
        else:
            logger.info(f"[Startup] GPU power limit: {result.stderr.strip()}")
    except Exception as e:
        logger.warning(f"[Startup] No se pudo configurar GPU: {e}")
    start_watchdog()
    _ensure_models_available()
    ace_available = _ensure_acestep_available()
    if ace_available:
        logger.info("[Startup] ✅ ACE-Step 1.5 disponible como segunda opción de modelo")
    else:
        logger.info("[Startup] ⚠️ ACE-Step no disponible — solo YuE estará activo")
    logger.info("[Startup] 🐕 GPU Watchdog iniciado — monitoreando VRAM y temperatura")

jobs = {}

# Tags que YuE entiende como secciones válidas
VALID_SECTION_TAGS = {'verse', 'chorus', 'bridge', 'intro', 'outro'}

# ============================================================
# FASE 0.1: Parámetros de inferencia optimizados
# ============================================================
YUE_PARAMS = {
    "max_new_tokens": 3000,       # Aumentado de 1500 → 3000 para canciones más largas (~60-90s audio)
    "run_n_segments": 2,          # 2 segmentos (balance entre duración y VRAM)
    "repetition_penalty": 1.1,    # Evitar loops
    "stage2_batch_size": 1,       # Reducido de 4 → 1 (crítico para VRAM)
    "rescale": True,              # Evitar clipping en la salida
}

# FASE 0.3: Configuración de multi-variante
VARIANT_CONFIG = {
    "enabled": True,              # Generar múltiples variantes
    "count": 1,                   # 1 variante para no saturar GPU (OOM con 2)
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
        "ace_step_ready": os.path.exists(f"{ACESTEP_DIR}/acestep"),
        "yue_script": yue_script,
        "yue_files": yue_files[:20],
        "model_files": model_files,
        "diagnostics": diagnostics,
        "variant_config": VARIANT_CONFIG,
        "yue_params": YUE_PARAMS,
        "models_available": {
            "yue": os.path.exists(f"{MODELS_DIR}/YuE-s1") and yue_script is not None,
            "ace_step": os.path.exists(f"{ACESTEP_DIR}/acestep"),
        },
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
    model = req.get("model", "yue")
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

    # === Common prompt processing ===
    embedded_style = extract_style_from_lyrics(lyrics)
    if embedded_style and not style_prompt:
        style_prompt = embedded_style
    elif embedded_style and style_prompt:
        style_prompt = f"{style_prompt}, {embedded_style}"

    # Fallback de estilo si sigue vacío
    if not style_prompt.strip():
        style_prompt = "pop rock, melodic male vocal, energetic"

    # 🎨 PROMPT ENRICHMENT
    original_prompt = style_prompt
    style_prompt = enrich_style_prompt(style_prompt)
    logger.info(f"[Generate] Prompt enriquecido: '{original_prompt}' → '{style_prompt}'")

    # Sanitizar la letra
    clean_lyrics = sanitize_lyrics(lyrics)

    # Generate seeds
    seeds = []
    for i in range(num_variants):
        if VARIANT_CONFIG["seeds"] == "random":
            seeds.append(random.randint(1, 999999))
        else:
            seeds.append(42 + i)

    # ============================================================
    # === ACE-STEP DISPATCH ===
    # ============================================================
    if model == "ace-step":
        if not os.path.exists(ACESTEP_DIR) or not os.path.exists(f"{ACESTEP_DIR}/acestep"):
            return {
                "status": "error",
                "message": "ACE-Step no está instalado en el servidor. Contacta al administrador.",
                "model_status": "unavailable",
            }

        logger.info(f"[Generate] Job {job_id} | Model: ACE-Step 1.5 | Style: '{style_prompt}' | Variants: {num_variants}")

        jobs[job_id] = {
            "status": "generating",
            "audio_url": None,
            "logs": [
                f"🎯 Generando {num_variants} variante(s) con ACE-Step 1.5",
                f"Seeds: {seeds}",
                f"Style: {style_prompt}",
            ],
            "variants": [],
            "num_variants": num_variants,
            "completed_variants": 0,
            "seeds": seeds,
            "model": "ace-step",
        }

        background_tasks.add_task(
            run_acestep_inference,
            job_id, clean_lyrics, style_prompt, seeds
        )

        return {
            "status": "success",
            "job_id": job_id,
            "generated_lyrics": clean_lyrics,
            "audio_url": None,
            "message": f"🎵 Generando {num_variants} variante(s) con ACE-Step 1.5...",
            "model_status": "generating",
            "num_variants": num_variants,
            "seeds": seeds,
        }

    # ============================================================
    # === YuE PATH (default) ===
    # ============================================================
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

    logger.info(f"[Generate] Job {job_id} | Model: YuE 7B | Style: '{style_prompt}' | Variants: {num_variants} | Lyrics sections: {clean_lyrics.count('[')} tags")

    # Initialize job with variant tracking
    jobs[job_id] = {
        "status": "generating",
        "audio_url": None,
        "logs": [
            f"🎯 Generando {num_variants} variante(s) con seeds: {seeds}",
            f"Style: {style_prompt}",
        ],
        "variants": [],
        "num_variants": num_variants,
        "completed_variants": 0,
        "seeds": seeds,
        "model": "yue",
    }

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

    # CWD = /opt/YuE/inference (donde están mm_tokenizer_v0.2_hf/, xcodec_mini_infer/, etc.)
    # PYTHONPATH ya incluye /opt/YuE/inference/xcodec_mini_infer para que models/ sea importable
    cwd = yue_inference_dir

    cmd = [
        "python3", "infer.py",
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
    env["TRANSFORMERS_ATTN_IMPLEMENTATION"] = "eager"
    env["FLASH_ATTENTION_FORCE_BUILD"] = "FALSE"

    # Parchar config de los modelos — SIEMPRE forzar eager attention (incondicional)
    for model_dir in [f"{MODELS_DIR}/YuE-s1", f"{MODELS_DIR}/YuE-s2"]:
        config_path = f"{model_dir}/config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.loads(f.read())
                # SIEMPRE forzar eager, sin importar el valor actual
                config['_attn_implementation'] = 'eager'
                config['attn_implementation'] = 'eager'
                with open(config_path, 'w') as f:
                    f.write(json.dumps(config, indent=2))
                logger.info(f"[Inference] ✅ Forced eager attention in {config_path}")
            except Exception as e:
                logger.warning(f"[Inference] No se pudo parchar {config_path}: {e}")

    # También parchar infer.py antes de cada inferencia
    _patch_infer_py()
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

                # Store PID for subprocess monitoring
                import time as _time
                jobs[job_id]["subprocess_pid"] = process.pid

                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        prefix = f"[{variant_label}]"
                        print(f"[{job_id}] {prefix} {clean_line}")
                        jobs[job_id]["logs"].append(f"{prefix} {clean_line}")
                        jobs[job_id]["last_log_time"] = _time.time()
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


# ============================================================
# ACE-Step 1.5 — Inference via subprocess
# ============================================================
def run_acestep_inference(job_id: str, lyrics: str, style_prompt: str, seeds: list):
    """
    Run ACE-Step 1.5 inference via subprocess.
    Generates multiple variants with different seeds, applies mastering to each.
    """
    try:
        import time as _time

        tmp_dir = f"/app/tmp/{job_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        num_variants = len(seeds)
        variant_results = []

        for variant_idx, seed in enumerate(seeds):
            variant_label = f"V{variant_idx + 1}/{num_variants}"
            jobs[job_id]["logs"].append(f"🎵 ACE-Step: Iniciando variante {variant_label} (seed={seed})...")

            variant_output = f"{OUTPUT_DIR}/{job_id}/v{variant_idx + 1}"
            os.makedirs(variant_output, exist_ok=True)
            output_wav = f"{variant_output}/raw.wav"

            # Escape strings for safe embedding in Python script
            safe_prompt = style_prompt.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')
            safe_lyrics = lyrics.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')

            # Build inline inference script using real ACE-Step API
            # API: ACEStepPipeline(checkpoint_dir, device_id=0, dtype="bfloat16", cpu_offload=False)
            # Call: pipeline(prompt, lyrics, audio_duration, infer_step, guidance_scale, ..., save_path)
            infer_script = f'''
import sys
sys.path.insert(0, "{ACESTEP_DIR}")

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
print(f"CUDA available: {{torch.cuda.is_available()}}", flush=True)
if torch.cuda.is_available():
    print(f"GPU: {{torch.cuda.get_device_name(0)}}", flush=True)
    print(f"VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}} GB", flush=True)

# Import ACE-Step pipeline (correct module name)
from acestep.pipeline_ace_step import ACEStepPipeline

print("Loading ACE-Step model (first time downloads ~7GB)...", flush=True)
pipeline = ACEStepPipeline(
    checkpoint_dir="{ACESTEP_MODEL_DIR}",
    device_id=0,
    dtype="bfloat16",
    cpu_offload=True,
)

print("Generating audio...", flush=True)
output_paths = pipeline(
    audio_duration=60.0,
    prompt="{safe_prompt}",
    lyrics="{safe_lyrics}",
    infer_step=60,
    guidance_scale=15.0,
    scheduler_type="euler",
    cfg_type="apg",
    omega_scale=10.0,
    manual_seeds=[{seed}],
    guidance_interval=0.5,
    guidance_interval_decay=0.0,
    min_guidance_scale=3.0,
    use_erg_tag=True,
    use_erg_lyric=True,
    use_erg_diffusion=True,
    save_path="{output_wav}",
)

print(f"Output paths: {{output_paths}}", flush=True)

# The pipeline saves the wav file directly via save_path
# output_paths is a list: [wav_path, ..., input_params_json_path]
if output_paths and os.path.exists(output_paths[0]):
    # Copy to expected location if different
    import shutil
    src = output_paths[0]
    if src != "{output_wav}":
        shutil.copy2(src, "{output_wav}")
    print(f"Audio saved: {{os.path.getsize('{output_wav}')}} bytes", flush=True)
    print("GENERATION_COMPLETE", flush=True)
else:
    print(f"ERROR: No output file generated. output_paths={{output_paths}}", flush=True)
    sys.exit(1)
'''
            script_path = f"{tmp_dir}/acestep_v{variant_idx}.py"
            with open(script_path, 'w') as f:
                f.write(infer_script)

            # Run subprocess
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{ACESTEP_DIR}:{env.get('PYTHONPATH', '')}"
            env["CUDA_VISIBLE_DEVICES"] = "0"
            env["PYTHONUNBUFFERED"] = "1"

            logger.info(f"[ACE-Step] 🚀 Variant {variant_label} | Seed: {seed}")

            process = subprocess.Popen(
                ["python3", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )

            jobs[job_id]["subprocess_pid"] = process.pid

            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    prefix = f"[ACE-{variant_label}]"
                    jobs[job_id]["logs"].append(f"{prefix} {clean_line}")
                    jobs[job_id]["last_log_time"] = _time.time()

            process.wait()

            if process.returncode == 0 and os.path.exists(output_wav):
                # Apply mastering pipeline
                jobs[job_id]["logs"].append(f"🎚️ Masterizando variante {variant_label}...")
                final_path = _finalize_audio(output_wav, job_id, variant_idx)

                if variant_idx == 0:
                    audio_url = f"/outputs/{job_id}.mp3"
                else:
                    audio_url = f"/outputs/{job_id}_v{variant_idx + 1}.mp3"

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
                    f"✅ ACE-Step variante {variant_label} lista: {metrics.get('duration_seconds', 0):.1f}s, "
                    f"LUFS: {metrics.get('lufs', 0):.1f}"
                )
            else:
                jobs[job_id]["logs"].append(f"❌ ACE-Step variante {variant_label} falló (code {process.returncode})")
                variant_results.append({
                    "index": variant_idx,
                    "seed": seed,
                    "audio_url": None,
                    "error": f"Process failed with code {process.returncode}",
                })

            jobs[job_id]["completed_variants"] = variant_idx + 1

        # All variants complete - select the best
        jobs[job_id]["variants"] = variant_results
        successful = [v for v in variant_results if v.get("audio_url")]

        if successful:
            best = max(
                successful,
                key=lambda v: (
                    v.get("duration", 0),
                    -abs(v.get("lufs", 0) - (-14)),
                )
            )

            # Copy best variant as primary if not v1
            if best["index"] != 0 and best.get("audio_url"):
                import shutil
                best_source = f"{OUTPUT_DIR}/{job_id}_v{best['index'] + 1}.mp3"
                best_dest = f"{OUTPUT_DIR}/{job_id}.mp3"
                if os.path.exists(best_source):
                    shutil.copy2(best_source, best_dest)

            primary_url = f"/outputs/{job_id}.mp3"
            jobs[job_id].update({
                "status": "done",
                "audio_url": primary_url,
                "best_variant": best["index"],
            })
            jobs[job_id]["logs"].append(
                f"🏆 Mejor variante ACE-Step: V{best['index'] + 1} "
                f"(duración: {best.get('duration', 0):.1f}s, LUFS: {best.get('lufs', 0):.1f})"
            )
            jobs[job_id]["logs"].append("✅ Generación ACE-Step completada.")
        else:
            jobs[job_id].update({
                "status": "error",
                "error": "Todas las variantes ACE-Step fallaron.",
                "error_detail": "\n".join(v.get("error", "Unknown") for v in variant_results),
            })

    except Exception as e:
        logger.error(f"[ACE-Step] ❌ Error crítico: {e}", exc_info=True)
        jobs[job_id].update({"status": "error", "error": str(e)})


@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id, {"status": "not_found"})
    if job_id in jobs and jobs[job_id].get("status") == "generating":
        # Add real-time GPU stats
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                job["gpu_stats"] = {
                    "vram_used_mb": int(parts[0].strip()),
                    "vram_total_mb": int(parts[1].strip()),
                    "gpu_util_pct": int(parts[2].strip()),
                    "power_w": float(parts[3].strip()),
                }
        except Exception:
            pass

        # Check if subprocess is still running
        pid = jobs[job_id].get("subprocess_pid")
        if pid:
            try:
                os.kill(pid, 0)  # Check if process exists
                job["subprocess_alive"] = True
            except (ProcessLookupError, PermissionError):
                job["subprocess_alive"] = False
        else:
            job["subprocess_alive"] = False

        # Time since last log activity
        last_ts = jobs[job_id].get("last_log_time")
        if last_ts:
            import time as _time
            job["seconds_since_activity"] = int(_time.time() - last_ts)
    return job


@app.get("/api/gpu")
def gpu_status():
    """🐕 GPU Watchdog status endpoint — polled by frontend every 5s."""
    return get_watchdog_status()


@app.post("/api/enrich-preview")
def enrich_preview(req: dict):
    """Preview what the prompt enricher would produce for a given style or lyrics."""
    mode = req.get("mode", "style")
    
    if mode in ("tags_only", "improve"):
        # Lyrics enrichment modes
        lyrics = req.get("lyrics", "")
        if not lyrics.strip():
            return {"error": "No lyrics provided", "original": "", "enriched": "", "mode": mode, "changed": False}
        return get_lyrics_enrichment(lyrics, mode)
    else:
        # Style enrichment (default)
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
        # ACE-Step checks
        "acestep_dir": {"path": ACESTEP_DIR, "exists": os.path.exists(ACESTEP_DIR)},
        "acestep_repo": {"path": f"{ACESTEP_DIR}/acestep", "exists": os.path.exists(f"{ACESTEP_DIR}/acestep")},
        "acestep_model": {"path": ACESTEP_MODEL_DIR, "exists": os.path.exists(ACESTEP_MODEL_DIR)},
    }

    # Check if acestep is importable
    try:
        import acestep
        checks["acestep_importable"] = True
    except ImportError:
        checks["acestep_importable"] = False

    if os.path.exists(MODELS_DIR):
        checks["model_dir_contents"] = os.listdir(MODELS_DIR)

    inf_dir = f"{YUE_DIR}/inference"
    if os.path.exists(inf_dir):
        checks["yue_inference_contents"] = os.listdir(inf_dir)[:30]

    if os.path.exists(ACESTEP_DIR):
        checks["acestep_dir_contents"] = os.listdir(ACESTEP_DIR)[:20]

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
        "models_available": {
            "yue": os.path.exists(f"{MODELS_DIR}/YuE-s1") and find_yue_script() is not None,
            "ace_step": os.path.exists(f"{ACESTEP_DIR}/acestep"),
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
