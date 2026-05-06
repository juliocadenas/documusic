# 🗺️ Mapa de Infraestructura AI - Servidor Madrid

Este documento sirve como contexto maestro para agentes de IA. Describe la arquitectura, ubicación de modelos y flujos de trabajo del servidor de producción.

## 🖥️ Servidor: Madrid (Pop!_OS)
- **IP Tailscale:** `100.65.182.25`
- **Hardware:** NVIDIA GeForce RTX 5080 (16GB VRAM)
- **SO:** Linux Pop!_OS 22.04 LTS
- **Entorno:** Docker + NVIDIA Container Toolkit (CUDA 12.1)

---

## 🧠 AI Model Hub (Almacenamiento Central)
Para evitar duplicidad de gigas, todos los modelos viven en el host y se montan en contenedores vía volúmenes.

- **Ruta Host:** `~/AI_MODELS`
- **Estructura:**
  - `~/AI_MODELS/huggingface/`: Modelos GGUF, Transformers (YuE, Whisper, etc.)
  - `~/AI_MODELS/ollama/`: Modelos gestionados por Ollama (Llama3, Mistral, etc.)
- **Regla de Oro:** Siempre usar formatos **GGUF** (cuantizados) para maximizar la VRAM de la RTX 5080.

---

## 🛠️ Herramientas y Librerías Core
- **Inferencia LLM/Música:** `llama-cpp-python` (con soporte CUDA).
- **Backend:** FastAPI (Python 3.10+).
- **Frontend:** React + Vite (con Proxy configurado para evitar CORS).
- **Orquestación:** Docker Compose.
- **NLP/Lyrics:** Ollama (corriendo en el puerto 11434).

---

## 🚀 Proyectos Activos
### 1. DocuMusic
- **Repositorio:** `~/documusic`
- **Frontend:** React (Vite) en puerto 5173 (local) -> Proxy a 8000 (Madrid).
- **Backend:** FastAPI en puerto 8000 (Madrid).
- **Modelos usados:**
  - `YuE-7B (GGUF)` -> Ubicado en `~/AI_MODELS/huggingface/YuE-7B/`
  - `Llama3 (Ollama)` -> Para generación de letras.

---

## 📡 Protocolo de Conexión (CORS Bypass)
Para conectar un frontend local (Venezuela) con el backend de Madrid sin errores de CORS:
1. Usar **Tailscale** para visibilidad de IP.
2. Configurar **Vite Proxy** en `vite.config.js`:
   ```javascript
   server: {
     proxy: { '/api': 'http://100.65.182.25:8000' }
   }
   ```
3. En el frontend, usar rutas relativas: `axios.get('/api/status')`.

---

## 📝 Notas de Mantenimiento
- **Actualizar Código:** `git pull origin main && docker compose up -d --build`.
- **Ver Logs:** `docker logs documusic_backend --tail 50`.
- **Limpiar Docker:** `docker system prune -f` (usar con cuidado).
