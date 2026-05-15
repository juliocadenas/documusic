"""
HeartMuLa Engine
Motor basado en HeartMuLa-oss-3B — The Most Powerful Open-Source Music Generation Model
Ideal para: Canciones completas con voces, multilingual, alta adherencia a letras.
VRAM requerida: ~8-10GB (con lazy_load en GPU única)
Licencia: Apache 2.0 - Uso comercial permitido.

Componentes:
- HeartMuLa: Music language model (3B params) — genera música condicionada en lyrics + tags
- HeartCodec: 12.5Hz music codec — decodifica tokens a audio de alta fidelidad
- HeartTranscriptor: Whisper-based lyrics transcription (opcional)
"""
import logging
import os
import time
import torch
from engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)

# HeartMuLa paths (Docker container)
HEARTMULA_DIR = "/opt/heartlib"
HEARTMULA_CKPT_DIR = "/app/models/HeartMuLa"


class HeartMuLaEngine(BaseEngine):

    @property
    def name(self) -> str:
        return "heartmula"

    @property
    def description(self) -> str:
        return "HeartMuLa 3B — El modelo open-source más potente. Multilingual, alta adherencia a letras, calidad comparable a Suno."

    @property
    def capabilities(self) -> dict:
        return {
            "vocals": True,
            "lyrics_aware": True,
            "structure_aware": True,
            "multilingual": True,
            "max_duration_min": 4,
            "stereo": True,
            "vram_gb_required": 8,
            "quality": "studio",
            "license": "Apache 2.0",
            "tags_system": True,
            "lazy_load": True,
        }

    def load(self) -> None:
        if self.is_loaded:
            logger.info("[HeartMuLa] Modelo ya cargado, saltando.")
            return

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[HeartMuLa] Cargando modelo 3B en {self.device}...")

        try:
            # HeartMuLa se carga via su propio pipeline
            # Verificar que el repo está instalado
            if not os.path.exists(HEARTMULA_DIR):
                raise ImportError(
                    f"HeartMuLa no encontrado en {HEARTMULA_DIR}. "
                    "Clona el repo: git clone https://github.com/HeartMuLa/heartlib.git /opt/heartlib"
                )

            # Verificar checkpoints
            if not os.path.exists(f"{HEARTMULA_CKPT_DIR}/HeartMuLa-oss-3B"):
                raise ImportError(
                    f"Checkpoints no encontrados en {HEARTMULA_CKPT_DIR}. "
                    "Descarga: hf download --local-dir './ckpt' 'HeartMuLa/HeartMuLaGen' && "
                    "hf download --local-dir './ckpt/HeartMuLa-oss-3B' 'HeartMuLa/HeartMuLa-oss-3B-happy-new-year' && "
                    "hf download --local-dir './ckpt/HeartCodec-oss' HeartMuLa/HeartCodec-oss-20260123"
                )

            self.is_loaded = True
            logger.info(f"[HeartMuLa] ✅ Modelo verificado. Checkpoints en {HEARTMULA_CKPT_DIR}")

        except ImportError:
            logger.error("[HeartMuLa] ❌ HeartMuLa no está instalado o faltan checkpoints.")
            raise
        except Exception as e:
            logger.error(f"[HeartMuLa] ❌ Error al cargar: {e}")
            raise

    def unload(self) -> None:
        if self.model:
            logger.info("[HeartMuLa] Descargando modelo de memoria...")
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.is_loaded = False
            logger.info("[HeartMuLa] ✅ Modelo descargado. VRAM liberada.")

    def generate(self, style_prompt: str, lyrics: str, duration_seconds: int = 60) -> str:
        """
        Genera audio usando HeartMuLa via subprocess (siguiendo el patrón de YuE/ACE-Step).
        
        HeartMuLa usa un sistema de lyrics + tags:
        - lyrics: Archivo .txt con la letra estructurada ([Verse], [Chorus], etc.)
        - tags: Archivo .txt con tags de estilo (genre, mood, instrument, bpm)
        
        Returns:
            Ruta absoluta al archivo de audio generado
        """
        if not self.is_loaded:
            self.load()

        output_path = f"temp_heartmula_{int(time.time())}.mp3"
        logger.info(f"[HeartMuLa] Generando audio ({duration_seconds}s). Tags: '{style_prompt[:80]}...'")

        try:
            import subprocess
            import tempfile

            # Crear archivos temporales para lyrics y tags
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(lyrics)
                lyrics_file = f.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(style_prompt)
                tags_file = f.name

            # Construir comando de inferencia
            script_path = f"{HEARTMULA_DIR}/examples/run_music_generation.py"
            max_audio_ms = min(duration_seconds * 1000, 240000)  # Max 4 min

            cmd = [
                "python3", script_path,
                "--model_path", HEARTMULA_CKPT_DIR,
                "--version", "3B",
                "--lyrics", lyrics_file,
                "--tags", tags_file,
                "--save_path", output_path,
                "--max_audio_length_ms", str(max_audio_ms),
                "--topk", "50",
                "--temperature", "1.0",
                "--cfg_scale", "1.5",
                "--lazy_load", "true",
            ]

            # Ejecutar inferencia
            env = os.environ.copy()
            env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                cwd=HEARTMULA_DIR, env=env,
            )

            # Limpiar archivos temporales
            try:
                os.remove(lyrics_file)
                os.remove(tags_file)
            except Exception:
                pass

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"[HeartMuLa] ✅ Audio generado: {output_path}")
                return output_path
            else:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                logger.error(f"[HeartMuLa] ❌ Error en inferencia: {error_msg}")
                raise RuntimeError(f"HeartMuLa inference failed: {error_msg}")

        except Exception as e:
            logger.error(f"[HeartMuLa] ❌ Error en generate(): {e}")
            raise
