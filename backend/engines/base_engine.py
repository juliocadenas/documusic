"""
Base Engine Interface
Todos los motores de generación deben heredar de esta clase base.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseEngine(ABC):
    """Interfaz común para todos los motores de generación de música."""

    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.device = "cpu"

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del motor."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción del motor."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> dict:
        """
        Retorna las capacidades del motor.
        Ejemplo: {'vocals': True, 'lyrics_aware': True, 'max_duration_min': 10}
        """
        pass

    @abstractmethod
    def load(self) -> None:
        """Carga el modelo en memoria (VRAM/RAM)."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Libera el modelo de memoria."""
        pass

    @abstractmethod
    def generate(self, style_prompt: str, lyrics: str, duration_seconds: int = 30) -> str:
        """
        Genera un segmento de audio.
        
        Args:
            style_prompt: Descripción del estilo musical
            lyrics: Letra o concepto para la sección
            duration_seconds: Duración en segundos
            
        Returns:
            Ruta absoluta al archivo WAV generado
        """
        pass
