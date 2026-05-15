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
from prompt_enricher import enrich_style_prompt, enrich_style_for_yue, get_enrichment_preview, get_lyrics_enrichment
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

        # 2. Parchar from_pretrained() con conditional 8-bit/16-bit quantization
        import re
        if 'yue_cond_quant_v2_applied' not in content and 'yue_cond_quant_v3_applied' not in content:
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
                # Build replacement with conditional 8-bit/16-bit quantization
                # YUE_USE_8BIT env var controls which path is used at runtime
                new_call = (
                    f'(AutoModelForCausalLM.from_pretrained(\n'
                    f'    {model_arg}, attn_implementation="eager", load_in_8bit=True, device_map="auto",\n'
                    f') if os.environ.get(\'YUE_USE_8BIT\', \'1\') == \'1\' else\n'
                    f'AutoModelForCausalLM.from_pretrained(\n'
                    f'    {model_arg}, attn_implementation="eager", torch_dtype=torch.bfloat16,\n'
                    f'))'
                )
                content = content[:start] + new_call + content[end+1:]
                patched = True
                logger.info(f"[Startup] infer.py: patched from_pretrained({model_arg}) → conditional 8-bit/16-bit")

            # Wrap model.to(device) in conditional — only for 16-bit mode
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                stripped = line.lstrip()
                if re.match(r'(model\w*\s*=\s*)?model\w*\.to\(', stripped) and '# [DocuMusic]' not in line:
                    indent = line[:len(line) - len(stripped)]
                    new_lines.append(f'{indent}if os.environ.get(\'YUE_USE_8BIT\', \'1\') != \'1\': {stripped} # [DocuMusic] conditional .to(device)')
                    patched = True
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)

            content += "\n# yue_cond_quant_v2_applied = True\n"

        # 2b. Fix .to(device) — un-comment old patches and wrap in conditional
        # This is a separate step because the old v1 patch commented out .to(device)
        # and the v2 patch above couldn't find them (they were already commented)
        if 'yue_to_device_conditional_applied' not in content:
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                stripped = line.lstrip()
                # Match commented-out .to(device) from old v1 patch:
                # "# model.to(device) # [DocuMusic] incompatible with device_map="auto""
                if re.match(r'#\s*(model\w*\s*=\s*)?model\w*\.to\(', stripped) and '[DocuMusic]' in line and 'incompatible' in line:
                    indent = line[:len(line) - len(stripped)]
                    # Extract the original uncommented code
                    uncommented = re.sub(r'^#\s*', '', stripped)
                    uncommented = re.sub(r'\s*#\s*\[DocuMusic\].*$', '', uncommented)
                    # Wrap in conditional
                    new_lines.append(f'{indent}if os.environ.get(\'YUE_USE_8BIT\', \'1\') != \'1\': {uncommented}  # [DocuMusic] conditional .to(device)')
                    patched = True
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
            content += "\n# yue_to_device_conditional_applied = True\n"

        # 2c. Wrap torch.cuda.empty_cache() in try/except — prevents CUDA crash after Stage1
        if 'yue_safe_empty_cache_applied' not in content:
            # Use regex to preserve indentation
            content = re.sub(
                r'^(\s*)torch\.cuda\.empty_cache\(\)',
                r'\1try:\n\1    torch.cuda.empty_cache()\n\1except Exception:\n\1    pass  # [DocuMusic] safe empty_cache',
                content,
                flags=re.MULTILINE
            )
            content += "\n# yue_safe_empty_cache_applied = True\n"
            patched = True
            logger.info("[Startup] infer.py: wrapped torch.cuda.empty_cache() in try/except")

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
    "max_new_tokens": 1500,       # 8-bit: 1500 seguro. 16-bit: OOM si >1000
    "run_n_segments": 4,          # 8-bit: 4 segmentos = ~60s. 16-bit: override a 2
    "repetition_penalty": 1.2,    # Aumentado de 1.1 → 1.2 para más variedad
    "stage2_batch_size": 1,       # Reducido de 4 → 1 (crítico para VRAM)
    "rescale": True,              # Evitar clipping en la salida
}

# Parámetros adaptativos según cuantización
YUE_PARAMS_BY_QUANT = {
    "8bit": {
        "max_new_tokens": 1500,
        "run_n_segments": 4,      # 4 segmentos × ~15s = ~60s
        "max_sections": 6,        # Permitir más secciones con 8-bit
    },
    "16bit": {
        "max_new_tokens": 1000,
        "run_n_segments": 2,      # 2 segmentos × ~15s = ~30s (límite VRAM)
        "max_sections": 4,        # Menos secciones para evitar OOM
    },
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


def _is_spanish(text: str) -> bool:
    """Detecta si un texto es principalmente español."""
    spanish_markers = [
        'que ', 'que\n', ' de ', ' la ', ' el ', ' en ', ' por ', ' con ',
        ' para ', ' un ', ' una ', ' los ', ' las ', ' del ', ' al ',
        ' está', ' tiene', ' puede', ' como', ' pero', ' más', ' todo',
        ' bien', ' muy', ' también', ' porque', ' hacia', ' desde',
        ' hasta', ' entre', ' sobre', ' después', ' antes', ' cada',
        ' todos', ' estas', ' este', ' esta', ' eso', ' esa', ' ese',
        ' vamos', ' cant', ' orgullo', ' agrade', ' disfrut',
        ' millones', ' archivos', ' estudio', ' conocimiento',
        ' fuentes', ' curso', ' estudiante', ' empleado',
        ' suscri', ' enseñ', ' clasific', ' brillante',
        ' increment', ' recurso', ' automatiz', ' industria',
        ' catalog', ' educaci', ' objetivo',
    ]
    text_lower = text.lower()
    matches = sum(1 for m in spanish_markers if m in text_lower)
    return matches >= 3


def _translate_to_english(text: str) -> tuple[str, bool]:
    """
    Traduce texto al inglés si está en español.
    Retorna (texto_traducido, fue_traducido).
    """
    if not _is_spanish(text):
        return text, False

    try:
        from deep_translator import GoogleTranslator
        # Translate line by line to preserve structure
        lines = text.split('\n')
        translated_lines = []
        translator = GoogleTranslator(source='es', target='en')

        for line in lines:
            stripped = line.strip()
            if not stripped:
                translated_lines.append('')
                continue
            # Don't translate section tags
            if stripped.startswith('[') and stripped.endswith(']'):
                translated_lines.append(stripped)
                continue
            try:
                translated = translator.translate(stripped)
                translated_lines.append(translated if translated else stripped)
            except Exception:
                translated_lines.append(stripped)

        result = '\n'.join(translated_lines)
        logger.info(f"[Translate] Spanish→English: {len(text)} chars → {len(result)} chars")
        return result, True
    except ImportError:
        logger.warning("[Translate] deep_translator not installed, skipping translation")
        return text, False
    except Exception as e:
        logger.warning(f"[Translate] Translation failed: {e}")
        return text, False


def sanitize_lyrics(lyrics: str) -> tuple[str, bool]:
    """
    Limpia la letra para que YuE la entienda correctamente.
    - Elimina tags de estilo como [Genre: ...], [Vocal: ...], etc.
    - Elimina tags numerados como [Verse 1], [Verse 2], etc.
    - Elimina prefijos numerados como "1.-", "2.-", etc.
    - Conserva solo secciones válidas: [verse], [chorus], [bridge], [intro], [outro]
    - Traduce español → inglés si es necesario (YuE anneal-en-cot = English only)
    - Garantiza que siempre haya al menos 2 secciones con ~4 líneas cada una

    Retorna (lyrics_formateadas, fue_traducida).
    """
    formatted = lyrics.strip()

    # 0. Detectar y traducir español → inglés
    formatted, was_translated = _translate_to_english(formatted)

    # 1. Eliminar tags numerados [Verse 1], [Chorus 2], etc. (antes del cleanup general)
    formatted = re.sub(
        r'\[(?:verse|chorus|bridge|intro|outro)\s+\d+\]',
        '',
        formatted,
        flags=re.IGNORECASE
    )

    # 2. Eliminar tags no estándar (cualquier [xxx] que NO sea exactamente [verse], [chorus], etc.)
    #    Usamos \] en vez de \b para solo permitir coincidencias exactas
    formatted = re.sub(
        r'\[(?!verse\]|chorus\]|bridge\]|intro\]|outro\])[^\]]+\]',
        '',
        formatted,
        flags=re.IGNORECASE
    )

    # 3. Eliminar prefijos numerados como "1.-", "2.-", "3.-", "N.", "N) "
    formatted = re.sub(r'^\s*\d+[\.\)\-]+\s*', '', formatted, flags=re.MULTILINE)

    # 4. Limpiar líneas vacías excesivas (máximo 2 saltos consecutivos)
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    # 5. Normalizar tags de sección a minúscula (YuE espera [verse] no [Verse])
    for tag in VALID_SECTION_TAGS:
        formatted = re.sub(
            rf'\[{tag}\]', f'[{tag}]',
            formatted,
            flags=re.IGNORECASE
        )

    # 6. Verificar si quedaron secciones válidas
    has_sections = any(
        f'[{tag}]' in formatted.lower()
        for tag in VALID_SECTION_TAGS
    )

    if not has_sections:
        lines = [l.strip() for l in formatted.split('\n') if l.strip()]
        if not lines:
            # Default lyrics template — substantial enough for YuE to generate vocals
            lines = [
                "Walking down this dusty road, sunset painting sky of gold",
                "Fences stretching mile on mile, this old land has got my soul",
                "Daddy taught me how to ride, mama sang me lullabies",
                "Country music in my blood, running deep as river tides",
                "Oh, this heart beats country time",
                "Steel guitar and whiskey wine",
                "Front porch swings and firefly lights",
                "Home is where the music shines",
                "Grandpa's fiddle in the barn, weathered hands but fingers warm",
                "Every note a memory, every song a family story",
                "Oh, this heart beats country time",
                "Steel guitar and whiskey wine",
                "Front porch swings and firefly lights",
                "Home is where the music shines",
            ]

        # Group into sections of ~4 lines (matching official YuE example format)
        section_size = 4
        sections = []
        for i in range(0, len(lines), section_size):
            chunk = lines[i:i + section_size]
            if chunk:
                sections.append(chunk)

        # Assign section types: verse, chorus, verse, chorus, bridge, chorus...
        section_types = []
        for i in range(len(sections)):
            if i == 0:
                section_types.append('verse')
            elif i == 1:
                section_types.append('chorus')
            elif i == 2:
                section_types.append('verse')
            elif i == 3:
                section_types.append('chorus')
            elif i == 4:
                section_types.append('bridge')
            else:
                section_types.append('chorus')

        parts = []
        for stype, slines in zip(section_types, sections):
            parts.append(f'[{stype}]\n' + '\n'.join(slines))

        # Always end with a final chorus if we have enough sections
        if len(sections) >= 2:
            parts.append('[chorus]\n' + '\n'.join(sections[1]))

        formatted = '\n\n'.join(parts)

    return formatted.strip(), was_translated


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
    # Safely check CUDA — wrap in try/except to survive CUDA crashes
    gpu_ok = False
    gpu_name = "RTX 5080"
    vram_free = "N/A"
    try:
        gpu_ok = torch.cuda.is_available()
        if gpu_ok:
            gpu_name = torch.cuda.get_device_name(0)
            vram_free = f"{torch.cuda.mem_get_info()[0] // 1024 ** 2} MB"
    except Exception:
        gpu_ok = False

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
        "gpu": gpu_name,
        "vram_free": vram_free,
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
    quantization = req.get("quantization", "16bit")
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

    # 🎨 PROMPT ENRICHMENT — use YuE-specific enrichment for YuE model
    original_prompt = style_prompt
    if model == "yue":
        style_prompt = enrich_style_for_yue(style_prompt)
    else:
        style_prompt = enrich_style_prompt(style_prompt)
    logger.info(f"[Generate] Prompt enriquecido ({model}): '{original_prompt}' → '{style_prompt}'")

    # Sanitizar la letra (ahora retorna tuple: (lyrics, was_translated))
    clean_lyrics, lyrics_translated = sanitize_lyrics(lyrics)
    if lyrics_translated:
        logger.info(f"[Generate] ⚠️ Lyrics traducidas español→inglés para modelo English-only")

    # === Parámetros adaptativos según cuantización ===
    quant_params = YUE_PARAMS_BY_QUANT.get(quantization, YUE_PARAMS_BY_QUANT["16bit"])
    max_sections = quant_params["max_sections"]
    adaptive_run_n_segments = quant_params["run_n_segments"]
    adaptive_max_tokens = quant_params["max_new_tokens"]

    # TRUNCAR lyrics al máximo de secciones permitido por la cuantización
    import re as _re
    sections = _re.split(r'(\[(?:verse|chorus|bridge|intro|outro)\])', clean_lyrics, flags=_re.IGNORECASE)
    reconstructed = []
    section_count = 0
    for part in sections:
        if _re.match(r'\[(?:verse|chorus|bridge|intro|outro)\]$', part, _re.IGNORECASE):
            section_count += 1
            if section_count > max_sections:
                break
        reconstructed.append(part)
    truncated_lyrics = ''.join(reconstructed).strip()
    if len(truncated_lyrics) < len(clean_lyrics):
        logger.info(f"[Generate] ✂️ Lyrics truncadas: {len(clean_lyrics)} → {len(truncated_lyrics)} chars ({section_count} secciones, max={max_sections} para {quantization})")
    clean_lyrics = truncated_lyrics

    # run_n_segments adaptativo: usar el menor entre el config y las secciones disponibles
    actual_sections = min(section_count, max_sections)
    dynamic_segments = min(adaptive_run_n_segments, max(actual_sections, 2))
    logger.info(f"[Generate] {quantization}: secciones={actual_sections}, run_n_segments={dynamic_segments}, max_new_tokens={adaptive_max_tokens}")

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
        job_id, clean_lyrics, style_prompt, yue_script, seeds, quantization,
        run_n_segments=dynamic_segments,
        max_new_tokens=adaptive_max_tokens,
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


def _build_inference_cmd(tmp_dir: str, output_path: str, yue_script: str, seed: int, run_n_segments: int = None, max_new_tokens: int = None) -> list:
    """Build the YuE inference command with optimized parameters (Fase 0.1)."""
    yue_inference_dir = os.path.dirname(yue_script) if "inference" in yue_script else "/opt/YuE/inference"

    # CWD = /opt/YuE/inference (donde están mm_tokenizer_v0.2_hf/, xcodec_mini_infer/, etc.)
    # PYTHONPATH ya incluye /opt/YuE/inference/xcodec_mini_infer para que models/ sea importable
    cwd = yue_inference_dir

    n_segs = run_n_segments if run_n_segments else YUE_PARAMS["run_n_segments"]
    n_tokens = max_new_tokens if max_new_tokens else YUE_PARAMS["max_new_tokens"]

    cmd = [
        "python3", "infer.py",
        "--stage1_model", f"{MODELS_DIR}/YuE-s1",
        "--stage2_model", f"{MODELS_DIR}/YuE-s2",
        "--genre_txt", f"{tmp_dir}/style.txt",
        "--lyrics_txt", f"{tmp_dir}/lyrics.txt",
        "--output_dir", output_path,
        "--cuda_idx", "0",
        # Parámetros adaptativos según cuantización
        "--max_new_tokens", str(n_tokens),
        "--run_n_segments", str(n_segs),
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


def _get_env(yue_inference_dir: str, quantization: str = "8bit") -> dict:
    """Get environment variables for YuE inference. quantization: '8bit' or '16bit'."""
    env = os.environ.copy()
    # Set YUE_USE_8BIT env var for conditional quantization in patched infer.py
    env["YUE_USE_8BIT"] = "1" if quantization == "8bit" else "0"
    # Reducir fragmentación de VRAM — crítico para evitar OOM en secuencias largas
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    logger.info(f"[Inference] Quantization: {quantization} (YUE_USE_8BIT={env['YUE_USE_8BIT']})")
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
    """Find the generated audio file, preferring the final mixed output.
    
    Search priority:
    1. _mixed files (final mix from YuE) - WAV preferred
    2. Any audio file in the output directory
    
    This avoids picking up individual stem files (vtrack.mp3, itrack.mp3)
    which are not the final mixed output.
    """
    # Collect ALL audio files (MP3 + WAV) at once
    all_files = []
    for pattern in [f"{output_path}/**/*.mp3", f"{output_path}/*.mp3",
                    f"{output_path}/**/*.wav", f"{output_path}/*.wav"]:
        all_files.extend(glob.glob(pattern, recursive=True))
    
    # Deduplicate while preserving order
    seen = set()
    unique_files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    
    if not unique_files:
        return None
    
    # Priority 1: _mixed files (final mix from YuE)
    mixed_files = [f for f in unique_files if '_mixed' in f]
    if mixed_files:
        # Prefer WAV over MP3 for mixed files (higher quality source)
        wav_mixed = [f for f in mixed_files if f.endswith('.wav')]
        if wav_mixed:
            logger.info(f"[Audio] Found mixed WAV: {wav_mixed[0]}")
            return wav_mixed[0]
        logger.info(f"[Audio] Found mixed file: {mixed_files[0]}")
        return mixed_files[0]
    
    # Priority 2: Any file (fallback)
    logger.warning(f"[Audio] No _mixed file found, using: {unique_files[0]} (total: {len(unique_files)} files)")
    return unique_files[0]


def _finalize_audio(source_path: str, job_id: str, variant_idx: int) -> str:
    """
    Convert/copy audio to final MP3 and apply mastering pipeline (Fase 0.2).
    Returns the path to the mastered MP3.
    """
    from audio_master import master_audio_simple

    if variant_idx == 0:
        # Primary variant: job_id.mp3
        final_mastered = f"{OUTPUT_DIR}/{job_id}.mp3"
        final_raw = f"{OUTPUT_DIR}/{job_id}_raw.mp3"
    else:
        # Additional variants: job_id_v2.mp3, job_id_v3.mp3
        final_mastered = f"{OUTPUT_DIR}/{job_id}_v{variant_idx + 1}.mp3"
        final_raw = f"{OUTPUT_DIR}/{job_id}_v{variant_idx + 1}_raw.mp3"

    # Convert to MP3 if needed — resample to 44.1kHz for better quality
    # YuE outputs at 16kHz which sounds muffled; upsampling improves clarity
    if source_path.endswith('.mp3'):
        subprocess.run(
            ["ffmpeg", "-y", "-i", source_path, "-ar", "44100", "-b:a", "192k", final_raw],
            check=True, capture_output=True
        )
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", source_path, "-ar", "44100", "-b:a", "192k", final_raw],
            check=True, capture_output=True
        )

    # FASE 0.2: Apply mastering pipeline
    try:
        mastered_path = master_audio_simple(final_raw, final_mastered)
        logger.info(f"[Master] ✅ Variant {variant_idx + 1} mastered: {mastered_path}")
        # Clean up intermediate raw file
        try:
            if final_raw != final_mastered and os.path.exists(final_raw):
                os.remove(final_raw)
        except Exception:
            pass
        return mastered_path
    except Exception as e:
        logger.warning(f"[Master] Mastering failed for variant {variant_idx + 1}: {e}")
        # Rename raw to final since mastering failed
        if final_raw != final_mastered:
            import shutil
            shutil.move(final_raw, final_mastered)
        return final_mastered


# ============================================================
# MULTI-PASS: Split lyrics, progressive preview, checkpoint/resume
# ============================================================

def _split_lyrics_into_chunks(lyrics: str, sections_per_chunk: int = 2) -> list:
    """Split lyrics into chunks of N sections each for multi-pass generation.
    
    Each chunk gets its own inference pass, allowing:
    - Progressive preview (listen as segments complete)
    - Checkpoint/resume (recover from failures)
    - Longer songs without OOM
    """
    import re as _re
    # Split by section tags, keeping the tags
    parts = _re.split(r'(\[(?:verse|chorus|bridge|intro|outro)\])', lyrics, flags=_re.IGNORECASE)
    chunks = []
    current_parts = []
    section_count = 0
    
    for part in parts:
        if _re.match(r'\[(?:verse|chorus|bridge|intro|outro)\]$', part, _re.IGNORECASE):
            if section_count >= sections_per_chunk and current_parts:
                chunk_text = ''.join(current_parts).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                current_parts = []
                section_count = 0
            section_count += 1
        current_parts.append(part)
    
    # Last chunk
    if current_parts:
        chunk_text = ''.join(current_parts).strip()
        if chunk_text:
            chunks.append(chunk_text)
    
    return chunks if chunks else [lyrics]


def _concatenate_audio_files(files: list, output_path: str) -> str:
    """Concatenate audio files using ffmpeg concat demuxer."""
    if not files:
        raise ValueError("No audio files to concatenate")
    if len(files) == 1:
        import shutil
        shutil.copy2(files[0], output_path)
        return output_path
    
    # Create concat list file
    list_path = output_path + '.list.txt'
    try:
        with open(list_path, 'w') as f:
            for fp in files:
                f.write(f"file '{fp}'\n")
        
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-ar", "44100", "-b:a", "192k", "-c:a", "libmp3lame", output_path],
            check=True, capture_output=True, timeout=60
        )
    finally:
        try:
            os.remove(list_path)
        except Exception:
            pass
    
    return output_path


def _save_checkpoint(job_id: str, data: dict):
    """Save checkpoint data for resume after failure."""
    checkpoint_dir = f"/app/tmp/{job_id}"
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = f"{checkpoint_dir}/checkpoint.json"
    with open(checkpoint_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"[Checkpoint] Saved for job {job_id}: {data.get('completed_segments', [])}")


def _load_checkpoint(job_id: str) -> dict | None:
    """Load checkpoint data for resume."""
    checkpoint_path = f"/app/tmp/{job_id}/checkpoint.json"
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Checkpoint] Failed to load for job {job_id}: {e}")
    return None


def _update_preview(job_id: str, segment_files: list, variant_idx: int):
    """Create/update preview MP3 from completed segments."""
    if not segment_files:
        return None
    
    try:
        preview_path = f"{OUTPUT_DIR}/{job_id}_preview.mp3"
        if variant_idx > 0:
            preview_path = f"{OUTPUT_DIR}/{job_id}_v{variant_idx + 1}_preview.mp3"
        
        _concatenate_audio_files(segment_files, preview_path)
        
        preview_url = f"/outputs/{os.path.basename(preview_path)}"
        jobs[job_id]["preview_url"] = preview_url
        logger.info(f"[Preview] Updated: {preview_url} ({len(segment_files)} segments)")
        return preview_url
    except Exception as e:
        logger.warning(f"[Preview] Failed to update: {e}")
        return None


def run_yue_inference_multi(job_id: str, lyrics: str, style_prompt: str, yue_script: str, seeds: list, quantization: str = "8bit", run_n_segments: int = None, max_new_tokens: int = None):
    """
    FASE 0.3: Multi-variant + Multi-pass generation with progressive preview.
    
    For each variant:
    - Splits lyrics into chunks (sections_per_chunk = run_n_segments)
    - Generates each chunk in a separate inference pass (multi-pass)
    - Provides progressive preview after each chunk completes
    - Saves checkpoints for resume after failures
    - Concatenates all chunks and applies mastering
    
    quantization: '8bit' or '16bit' — controls model loading behavior.
    run_n_segments: Override for YUE_PARAMS['run_n_segments'].
    max_new_tokens: Override for YUE_PARAMS['max_new_tokens'].
    """
    try:
        import time as _time

        tmp_dir = f"/app/tmp/{job_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        # Write full style prompt
        with open(f"{tmp_dir}/style.txt", "w", encoding="utf-8") as f:
            f.write(style_prompt)

        n_segs = run_n_segments if run_n_segments else YUE_PARAMS["run_n_segments"]
        n_tokens = max_new_tokens if max_new_tokens else YUE_PARAMS["max_new_tokens"]

        # === MULTI-PASS: Split lyrics into chunks ===
        chunks = _split_lyrics_into_chunks(lyrics, sections_per_chunk=n_segs)
        num_chunks = len(chunks)
        is_multipass = num_chunks > 1

        if is_multipass:
            jobs[job_id]["logs"].append(
                f"📋 Multi-pass: {num_chunks} segmentos × ~{n_segs} secciones c/u"
            )
            jobs[job_id]["total_segments"] = num_chunks
            jobs[job_id]["completed_segments"] = 0
            jobs[job_id]["segments"] = [
                {"index": i, "status": "pending", "audio_path": None, "duration": 0}
                for i in range(num_chunks)
            ]
        else:
            jobs[job_id]["total_segments"] = 1
            jobs[job_id]["completed_segments"] = 0

        num_variants = len(seeds)
        variant_results = []

        # === Load checkpoint for resume ===
        checkpoint = _load_checkpoint(job_id)
        resume_from_segment = 0
        resume_segment_files = []
        if checkpoint:
            resume_from_segment = checkpoint.get("completed_segments", 0)
            resume_segment_files = checkpoint.get("segment_files", [])
            jobs[job_id]["logs"].append(
                f"🔄 Reanudando desde segmento {resume_from_segment + 1}/{num_chunks} "
                f"({len(resume_segment_files)} archivos previos)"
            )

        for variant_idx, seed in enumerate(seeds):
            variant_label = f"V{variant_idx + 1}/{num_variants}"
            jobs[job_id]["logs"].append(f"🎵 Iniciando variante {variant_label} (seed={seed})...")

            variant_output = f"{OUTPUT_DIR}/{job_id}/v{variant_idx + 1}"
            os.makedirs(variant_output, exist_ok=True)

            segment_files = list(resume_segment_files) if variant_idx == 0 else []
            variant_error = False

            for chunk_idx, chunk_lyrics in enumerate(chunks):
                # Skip already completed segments on resume
                if chunk_idx < resume_from_segment:
                    continue

                seg_label = f"S{chunk_idx + 1}/{num_chunks}"
                full_label = f"{variant_label} {seg_label}"

                if is_multipass:
                    jobs[job_id]["logs"].append(f"🎤 Generando segmento {seg_label}...")
                    if "segments" in jobs[job_id]:
                        jobs[job_id]["segments"][chunk_idx]["status"] = "generating"

                # Write chunk-specific lyrics file
                chunk_lyrics_file = f"{tmp_dir}/lyrics_chunk{chunk_idx}.txt"
                with open(chunk_lyrics_file, "w", encoding="utf-8") as f:
                    f.write(chunk_lyrics.strip())

                # Count sections in this chunk for dynamic run_n_segments
                import re as _re
                chunk_sections = len(_re.findall(
                    r'\[(?:verse|chorus|bridge|intro|outro)\]', chunk_lyrics, _re.IGNORECASE
                ))
                chunk_segs = max(1, min(n_segs, chunk_sections)) if chunk_sections > 0 else n_segs

                # Build command for this chunk
                cmd, yue_inference_dir = _build_inference_cmd(
                    tmp_dir, variant_output, yue_script, seed, chunk_segs, n_tokens
                )
                # Replace lyrics file path to point to chunk file
                for i, arg in enumerate(cmd):
                    if arg == f"{tmp_dir}/lyrics.txt":
                        cmd[i] = chunk_lyrics_file
                        break

                env = _get_env(yue_inference_dir, quantization)
                logger.info(f"[YuE] 🚀 {full_label} | Seed: {seed} | Chunk sections: {chunk_sections} | run_n_segments: {chunk_segs}")

                # Run inference for this chunk
                error_lines = []
                try:
                    process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, cwd=yue_inference_dir, env=env,
                        bufsize=1, universal_newlines=True
                    )
                    jobs[job_id]["subprocess_pid"] = process.pid

                    for line in process.stdout:
                        clean_line = line.strip()
                        if clean_line:
                            prefix = f"[{full_label}]"
                            print(f"[{job_id}] {prefix} {clean_line}")
                            jobs[job_id]["logs"].append(f"{prefix} {clean_line}")
                            jobs[job_id]["last_log_time"] = _time.time()
                            if any(kw in clean_line.lower() for kw in ['error', 'traceback', 'exception', 'failed']):
                                error_lines.append(clean_line)

                    process.wait()

                    if process.returncode == 0:
                        source_path = _find_audio_file(variant_output)
                        if source_path:
                            # Convert to MP3 for concatenation
                            seg_mp3 = f"{variant_output}/segment_{chunk_idx}.mp3"
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", source_path, "-ar", "44100", "-b:a", "192k", seg_mp3],
                                check=True, capture_output=True
                            )
                            segment_files.append(seg_mp3)

                            # Update segment status
                            if "segments" in jobs[job_id]:
                                from audio_master import get_audio_metrics as _get_metrics
                                seg_metrics = _get_metrics(seg_mp3)
                                jobs[job_id]["segments"][chunk_idx] = {
                                    "index": chunk_idx, "status": "done",
                                    "audio_path": seg_mp3,
                                    "duration": seg_metrics.get("duration_seconds", 0),
                                }

                            jobs[job_id]["completed_segments"] = chunk_idx + 1

                            # === PROGRESSIVE PREVIEW ===
                            if is_multipass and segment_files:
                                _update_preview(job_id, segment_files, variant_idx)
                                jobs[job_id]["logs"].append(
                                    f"🎧 Preview actualizado: {len(segment_files)}/{num_chunks} segmentos"
                                )

                            # === CHECKPOINT ===
                            if is_multipass:
                                _save_checkpoint(job_id, {
                                    "job_id": job_id,
                                    "completed_segments": chunk_idx + 1,
                                    "total_segments": num_chunks,
                                    "segment_files": segment_files,
                                    "seed": seed,
                                    "quantization": quantization,
                                    "style_prompt": style_prompt,
                                })

                            # Clean variant output for next chunk
                            if chunk_idx < num_chunks - 1:
                                for f in glob.glob(f"{variant_output}/*"):
                                    if f not in segment_files:
                                        try: os.remove(f)
                                        except Exception: pass
                        else:
                            jobs[job_id]["logs"].append(f"⚠️ {full_label}: No se encontró audio")
                    else:
                        error_detail = "\n".join(error_lines[-5:]) if error_lines else "Unknown error"
                        jobs[job_id]["logs"].append(f"❌ {full_label} falló (code {process.returncode})")
                        variant_error = True

                except Exception as e:
                    jobs[job_id]["logs"].append(f"❌ {full_label} excepción: {e}")
                    variant_error = True

                # If chunk failed, save checkpoint and stop this variant
                if variant_error:
                    if is_multipass and segment_files:
                        _save_checkpoint(job_id, {
                            "job_id": job_id,
                            "completed_segments": chunk_idx,
                            "total_segments": num_chunks,
                            "segment_files": segment_files,
                            "seed": seed,
                            "quantization": quantization,
                            "style_prompt": style_prompt,
                            "failed_at_segment": chunk_idx,
                        })
                        jobs[job_id]["logs"].append(
                            f"💾 Checkpoint guardado. {len(segment_files)}/{num_chunks} segmentos. Puedes reanudar."
                        )
                    break

            # === POST-VARIANT: Concatenate segments if multi-pass ===
            if not variant_error and is_multipass and len(segment_files) > 1:
                jobs[job_id]["logs"].append(f"🔗 Concatenando {len(segment_files)} segmentos...")
                concat_path = f"{variant_output}/full_concat.mp3"
                try:
                    _concatenate_audio_files(segment_files, concat_path)
                    source_path = concat_path
                except Exception as e:
                    jobs[job_id]["logs"].append(f"⚠️ Error concatenando: {e}")
                    source_path = segment_files[-1] if segment_files else None
            elif not variant_error and segment_files:
                source_path = segment_files[0]
            else:
                source_path = None

            if not variant_error and source_path:
                # Apply mastering
                jobs[job_id]["logs"].append(f"🎚️ Masterizando variante {variant_label}...")
                final_path = _finalize_audio(source_path, job_id, variant_idx)

                audio_url = f"/outputs/{job_id}.mp3" if variant_idx == 0 else f"/outputs/{job_id}_v{variant_idx + 1}.mp3"

                from audio_master import get_audio_metrics
                metrics = get_audio_metrics(final_path)

                variant_results.append({
                    "index": variant_idx, "seed": seed, "audio_url": audio_url,
                    "duration": metrics.get("duration_seconds", 0),
                    "file_size": metrics.get("file_size_bytes", 0),
                    "lufs": metrics.get("lufs", 0),
                    "segments": len(segment_files),
                })
                jobs[job_id]["logs"].append(
                    f"✅ Variante {variant_label} lista: {metrics.get('duration_seconds', 0):.1f}s, "
                    f"LUFS: {metrics.get('lufs', 0):.1f}, {len(segment_files)} segmento(s)"
                )
            elif variant_error:
                variant_results.append({
                    "index": variant_idx, "seed": seed, "audio_url": None,
                    "error": "Segment(s) failed. Checkpoint saved for resume.",
                })
            else:
                variant_results.append({
                    "index": variant_idx, "seed": seed, "audio_url": None,
                    "error": "No audio generated",
                })

            jobs[job_id]["completed_variants"] = variant_idx + 1

        # === ALL VARIANTS COMPLETE ===
        successful_variants = [v for v in variant_results if v.get("audio_url")]
        jobs[job_id]["variants"] = variant_results

        if successful_variants:
            best = max(
                successful_variants,
                key=lambda v: (v.get("duration", 0), -abs(v.get("lufs", 0) - (-14)))
            )

            if best["index"] != 0 and best.get("audio_url"):
                import shutil
                best_source = f"{OUTPUT_DIR}/{job_id}_v{best['index'] + 1}.mp3"
                best_dest = f"{OUTPUT_DIR}/{job_id}.mp3"
                if os.path.exists(best_source):
                    shutil.copy2(best_source, best_dest)
                    variant_results[0] = {
                        "index": 0, "seed": seeds[0],
                        "audio_url": f"/outputs/{job_id}.mp3",
                        "duration": best.get("duration", 0),
                        "file_size": best.get("file_size_bytes", 0),
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
            has_checkpoint = any("Checkpoint" in (v.get("error", "")) for v in variant_results)
            error_msg = "Todas las variantes fallaron."
            if has_checkpoint:
                error_msg += " Se guardaron checkpoints para reanudar."
            jobs[job_id].update({
                "status": "error",
                "error": error_msg,
                "error_detail": "\n".join(v.get("error", "Unknown") for v in variant_results),
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
    torch.cuda.empty_cache()
    print(f"VRAM after cleanup: {{torch.cuda.mem_get_info()[0] / 1024**2:.0f}} MB free", flush=True)

# Import ACE-Step pipeline (correct module name)
from acestep.pipeline_ace_step import ACEStepPipeline

print("Loading ACE-Step model (cpu_offload for VRAM safety)...", flush=True)
pipeline = ACEStepPipeline(
    checkpoint_dir="{ACESTEP_MODEL_DIR}",
    device_id=0,
    dtype="bfloat16",
    cpu_offload=True,
)

print("Generating audio (60s, this may take several minutes)...", flush=True)
try:
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
except torch.cuda.CudaError as e:
    print(f"CUDA ERROR during generation: {{e}}", flush=True)
    torch.cuda.empty_cache()
    sys.exit(2)
except Exception as e:
    print(f"ERROR during generation: {{e}}", flush=True)
    sys.exit(1)

print(f"Output paths: {{output_paths}}", flush=True)

# Free VRAM immediately after generation
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    print(f"VRAM freed: {{torch.cuda.mem_get_info()[0] / 1024**2:.0f}} MB free", flush=True)

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
            ace_step_timeout = 600  # 10 minutes max per variant
            start_time = _time.time()

            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    prefix = f"[ACE-{variant_label}]"
                    jobs[job_id]["logs"].append(f"{prefix} {clean_line}")
                    jobs[job_id]["last_log_time"] = _time.time()

                # Check timeout
                elapsed = _time.time() - start_time
                if elapsed > ace_step_timeout:
                    jobs[job_id]["logs"].append(
                        f"[ACE-{variant_label}] TIMEOUT after {ace_step_timeout}s, killing process..."
                    )
                    process.kill()
                    break

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


@app.get("/api/jobs/history")
def get_jobs_history():
    """Lista todos los jobs completados (en memoria + escaneo de outputs)."""
    history = []
    
    # 1. Jobs en memoria con status "done"
    for job_id, job in jobs.items():
        if job.get("status") == "done":
            variants = job.get("variants", [])
            best = job.get("best_variant", 0)
            v = variants[best] if best < len(variants) else (variants[0] if variants else {})
            history.append({
                "job_id": job_id,
                "status": "done",
                "model": job.get("model", "yue"),
                "style": job.get("style_prompt", ""),
                "audio_url": job.get("audio_url"),
                "duration": v.get("duration", 0),
                "lufs": v.get("lufs", 0),
                "seed": v.get("seed"),
                "created": job.get("created", 0),
                "source": "memory",
            })
    
    # 2. Escanear outputs/ para MP3s no en memoria (persistidos)
    try:
        output_dir = "/app/outputs"
        existing_ids = set(jobs.keys())
        if os.path.isdir(output_dir):
            for f in sorted(os.listdir(output_dir), reverse=True):
                if f.endswith(".mp3") and not f.startswith("test_"):
                    # Extraer job_id del nombre (formato: {job_id}.mp3 o {job_id}_raw.mp3)
                    job_id = f.replace("_raw.mp3", "").replace(".mp3", "")
                    if job_id in existing_ids:
                        continue
                    filepath = os.path.join(output_dir, f)
                    try:
                        file_stat = os.stat(filepath)
                        # Get duration with ffprobe
                        dur = 0
                        try:
                            result = subprocess.run(
                                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", filepath],
                                capture_output=True, text=True, timeout=5
                            )
                            if result.returncode == 0 and result.stdout.strip():
                                dur = float(result.stdout.strip())
                        except Exception:
                            pass
                        history.append({
                            "job_id": job_id,
                            "status": "done",
                            "model": "unknown",
                            "style": "",
                            "audio_url": f"/outputs/{f}",
                            "duration": dur,
                            "lufs": 0,
                            "seed": None,
                            "created": file_stat.st_ctime,
                            "file_size": file_stat.st_size,
                            "source": "disk",
                        })
                        existing_ids.add(job_id)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"[History] Error scanning outputs: {e}")
    
    # Sort by creation time (newest first)
    history.sort(key=lambda x: x.get("created", 0), reverse=True)
    return {"jobs": history, "total": len(history)}


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
