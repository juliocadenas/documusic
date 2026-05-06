# DocuMusic AI Engine 🎵

Sistema de generación musical por IA optimizado para GPUs NVIDIA (RTX 5080). Utiliza YuE para generación completa y Ollama para procesamiento de lenguaje.

## Arquitectura
- **Backend:** FastAPI corriendo en Docker.
- **Modelos:** YuE (7B) cuantizado en 4-bit para optimización de VRAM.
- **Hub de Modelos:** Carpeta centralizada en `~/AI_MODELS` para evitar duplicidad.

## Instalación Rápida

1. Asegúrate de tener instalados los drivers de NVIDIA y el NVIDIA Container Toolkit.
2. Clona este repositorio.
3. Lanza el sistema completo:
   ```bash
   docker compose up -d --build
   ```

## Endpoints
- `GET /`: Estado del sistema y GPU.
- `POST /generate-music`: Generación de música mediante prompts.
