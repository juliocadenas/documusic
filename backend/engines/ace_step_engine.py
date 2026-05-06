"""
ACE-Step Engine
Motor basado en ACE-Step 1.5 (STEPFUN-IO)
Ideal para: Canciones completas hasta 10 min, voces, multi-instrumentación.
VRAM requerida: ~8GB (Base) / ~14GB (XL)
Licencia: Apache 2.0 - Uso comercial permitido.
"""
import logging
import os
import time
import torch
from engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)


class AceStepEngine(BaseEngine):

    @property
    def name(self) -> str:
        return "ace-step"

    @property
    def description(self) -> str:
        return "ACE-Step 1.5 — Canciones completas con voces y multi-instrumentación (hasta 10 min). Licencia Apache 2.0."

    @property
    def capabilities(self) -> dict:
        return {
            "vocals": True,
            "lyrics_aware": True,
            "max_duration_min": 10,
            "stereo": True,
            "vram_gb_required": 8,
            "quality": "studio",
            "license": "Apache 2.0"
        }

    def load(self) -> None:
        if self.is_loaded:
            logger.info("[AceStep] Modelo ya cargado, saltando.")
            return

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[AceStep] Cargando modelo en {self.device}...")

        try:
            # Importar las dependencias propias de ACE-Step
            # Requiere tener ACE-Step clonado en /app/engines/ace_step_src/
            # o instalado como paquete: pip install ace-step
            from ace_step.pipeline import ACEStepPipeline  # type: ignore

            self.model = ACEStepPipeline.from_pretrained(
                "STEPFUN-IO/ACE-Step-v1.5-3.5B",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            ).to(self.device)

            self.is_loaded = True
            logger.info(f"[AceStep] ✅ Modelo cargado correctamente en {self.device}.")

        except ImportError:
            logger.error("[AceStep] ❌ ACE-Step no está instalado. Instálalo con: pip install ace-step")
            raise
        except Exception as e:
            logger.error(f"[AceStep] ❌ Error al cargar: {e}")
            raise

    def unload(self) -> None:
        if self.model:
            logger.info("[AceStep] Descargando modelo de memoria...")
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.is_loaded = False
            logger.info("[AceStep] Modelo descargado.")

    def generate(self, style_prompt: str, lyrics: str, duration_seconds: int = 60) -> str:
        if not self.is_loaded:
            self.load()

        output_path = f"temp_ace_{int(time.time())}.wav"
        logger.info(f"[AceStep] Generando audio ({duration_seconds}s) con prompt: '{style_prompt[:50]}...'")

        try:
            # ACE-Step acepta prompt de estilo y letra directamente
            result = self.model(
                prompt=style_prompt,
                lyrics=lyrics,
                duration=duration_seconds,
                guidance_scale=7.0,
                num_inference_steps=50,
            )

            # Guardar el audio resultante
            result.save(output_path)
            logger.info(f"[AceStep] ✅ Audio generado: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[AceStep] ❌ Error en generate(): {e}")
            raise
