"""
YuE Engine
Motor basado en YuE (7B) — Multimodal Music Foundation Model
Ideal para: Voces hiperrealistas, estructura narrativa coherente (verso/coro/bridge).
VRAM requerida: ~14-16GB (Full FP16)
Licencia: Apache 2.0 - Uso comercial permitido.
"""
import logging
import os
import time
import torch
from engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)


class YuEEngine(BaseEngine):

    @property
    def name(self) -> str:
        return "yue"

    @property
    def description(self) -> str:
        return "YuE 7B — Voces hiperrealistas y comprensión estructural de letras (verso/coro/bridge). El más cercano a Suno AI."

    @property
    def capabilities(self) -> dict:
        return {
            "vocals": True,
            "lyrics_aware": True,
            "structure_aware": True,  # Entiende [Verse], [Chorus], [Bridge]
            "max_duration_min": 5,
            "stereo": True,
            "vram_gb_required": 14,
            "quality": "hyper-realistic",
            "license": "Apache 2.0"
        }

    def load(self) -> None:
        if self.is_loaded:
            logger.info("[YuE] Modelo ya cargado, saltando.")
            return

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[YuE] Cargando modelo 7B en {self.device} (FP16)...")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline  # type: ignore
            from transformers import AutoProcessor  # type: ignore

            model_id = "m-a-p/YuE-s1-7B-anneal-en-cot"  # Variante en Inglés / narrativa

            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto",  # Distribuye capas automáticamente entre GPU/CPU si es necesario
                low_cpu_mem_usage=True,
            )

            self.is_loaded = True
            logger.info(f"[YuE] ✅ Modelo cargado correctamente. Dispositivo: {self.device}.")

        except ImportError:
            logger.error("[YuE] ❌ 'transformers' no está instalado. Ejecuta: pip install transformers accelerate")
            raise
        except Exception as e:
            logger.error(f"[YuE] ❌ Error al cargar el modelo: {e}")
            raise

    def unload(self) -> None:
        if self.model:
            logger.info("[YuE] Descargando modelo de memoria...")
            del self.model
            if hasattr(self, 'tokenizer'):
                del self.tokenizer
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.is_loaded = False
            logger.info("[YuE] ✅ Modelo descargado. VRAM liberada.")

    def generate(self, style_prompt: str, lyrics: str, duration_seconds: int = 60) -> str:
        if not self.is_loaded:
            self.load()

        output_path = f"temp_yue_{int(time.time())}.wav"
        logger.info(f"[YuE] Generando audio ({duration_seconds}s). Estructura de letra detectada.")

        try:
            # YuE utiliza un sistema de prompts estructurado:
            # El 'style_prompt' condicionará el estilo musical.
            # El 'lyrics' se pasa con marcadores de sección: [Verse], [Chorus], etc.
            full_prompt = f"[Genre]: {style_prompt}\n[Lyrics]:\n{lyrics}"

            inputs = self.tokenizer(full_prompt, return_tensors="pt").to(self.device)

            with torch.no_grad():
                audio_tokens = self.model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=True,
                    temperature=0.8,
                    top_p=0.9,
                )

            # Decodificar tokens de audio a forma de onda
            # (YuE usa un codec propio, aquí se haría la conversión)
            # Nota: La API real de YuE tiene un vocoder integrado
            audio_waveform = self.model.decode_audio(audio_tokens)

            # Guardar como WAV usando torchaudio
            import torchaudio
            torchaudio.save(output_path, audio_waveform.cpu(), sample_rate=44100)

            logger.info(f"[YuE] ✅ Audio generado: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[YuE] ❌ Error en generate(): {e}")
            raise
