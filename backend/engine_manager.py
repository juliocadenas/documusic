"""
Engine Manager
Gestiona el ciclo de vida de los motores de generación.
Permite cambiar de motor en caliente liberando VRAM entre cambios.
"""
import logging
from typing import Optional
from engines.base_engine import BaseEngine
from engines.yue_engine import YuEEngine
from engines.ace_step_engine import AceStepEngine

logger = logging.getLogger(__name__)

# Registro de todos los motores disponibles
AVAILABLE_ENGINES: dict[str, type[BaseEngine]] = {
    "yue":      YuEEngine,
    "ace-step": AceStepEngine,
}


class EngineManager:
    """
    Gestor Singleton de motores de IA.
    Garantiza que solo un motor esté cargado en VRAM a la vez,
    descargando el anterior antes de cargar uno nuevo.
    """

    def __init__(self):
        self._current_engine: Optional[BaseEngine] = None
        self._current_engine_name: Optional[str] = None

    @property
    def current_engine_name(self) -> Optional[str]:
        return self._current_engine_name

    @property
    def current_engine(self) -> Optional[BaseEngine]:
        return self._current_engine

    def get_available_engines(self) -> list[dict]:
        """Retorna la lista de motores disponibles con sus metadatos."""
        result = []
        for engine_name, engine_class in AVAILABLE_ENGINES.items():
            instance = engine_class()
            result.append({
                "id": engine_name,
                "name": engine_name.upper(),
                "description": instance.description,
                "capabilities": instance.capabilities,
                "is_active": engine_name == self._current_engine_name,
            })
        return result

    def switch_engine(self, engine_name: str) -> dict:
        """
        Cambia el motor activo.
        Descarga el motor anterior de VRAM antes de cargar el nuevo.
        """
        if engine_name not in AVAILABLE_ENGINES:
            raise ValueError(f"Motor '{engine_name}' no encontrado. Opciones: {list(AVAILABLE_ENGINES.keys())}")

        if engine_name == self._current_engine_name and self._current_engine and self._current_engine.is_loaded:
            logger.info(f"[EngineManager] Motor '{engine_name}' ya está activo.")
            return {"status": "already_active", "engine": engine_name}

        # Descargar motor anterior para liberar VRAM
        if self._current_engine and self._current_engine.is_loaded:
            logger.info(f"[EngineManager] Descargando motor anterior: {self._current_engine_name}...")
            self._current_engine.unload()
            self._current_engine = None

        # Instanciar y cargar el nuevo motor
        logger.info(f"[EngineManager] Cargando motor: {engine_name}...")
        engine_class = AVAILABLE_ENGINES[engine_name]
        self._current_engine = engine_class()
        self._current_engine.load()

        self._current_engine_name = engine_name
        logger.info(f"[EngineManager] ✅ Motor '{engine_name}' listo.")

        return {
            "status": "switched",
            "engine": engine_name,
            "capabilities": self._current_engine.capabilities
        }

    def generate(self, style_prompt: str, lyrics: str, duration_seconds: int = 60) -> str:
        """Delega la generación al motor activo."""
        if not self._current_engine or not self._current_engine.is_loaded:
            raise RuntimeError("Ningún motor está cargado. Llama a /engine/switch primero.")

        return self._current_engine.generate(style_prompt, lyrics, duration_seconds)

    def get_status(self) -> dict:
        """Retorna el estado actual del gestor."""
        if not self._current_engine:
            return {"status": "idle", "engine": None}

        return {
            "status": "ready" if self._current_engine.is_loaded else "unloaded",
            "engine": self._current_engine_name,
            "capabilities": self._current_engine.capabilities if self._current_engine.is_loaded else {},
            "device": self._current_engine.device,
        }


# Instancia global (Singleton)
engine_manager = EngineManager()
