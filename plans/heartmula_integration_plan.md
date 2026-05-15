# 🎵 Plan de Integración: HeartMuLa → DocuMusic

## 📋 Contexto y Problema

### Problemas con YuE 7B
- **Intro excesiva**: 35 segundos de intro en generación de 45s
- **Letra ignorada**: Solo pronuncia 2 palabras de toda la letra
- **Calidad inconsistente**: Resultados impredecibles
- **Pesado**: 7B parámetros, ~14-16GB VRAM

### Por qué HeartMuLa
| Característica | YuE 7B | HeartMuLa 3B |
|---|---|---|
| Parámetros | 7B | 3B (más ligero) |
| VRAM requerida | ~14-16GB | ~8-10GB (con lazy_load) |
| Licencia | Apache 2.0 | Apache 2.0 |
| Multilingual | Limitado | Casi todos los idiomas |
| Calidad vocal | Inconsistente | Superior (benchmark propio) |
| Adherencia a letra | Pobre (2 palabras) | Alta (diseñado para ello) |
| Tags/Estilo | Básico | Sistema de tags robusto |
| Codec | xcodec (problemático) | HeartCodec (12.5Hz, alta fidelidad) |
| Stars GitHub | ~2,000 | 3,577 |
| 7B interno vs Suno | No comparable | Comparable con Suno |

---

## 🏗️ Decisión de Arquitectura: Integrar en DocuMusic Existente

### ✅ Integrar (NO crear interfaz nueva)

**Razones:**
1. **`BaseEngine`** ya define la interfaz perfecta — solo necesitamos crear `HeartMuLaEngine`
2. **`EngineManager`** ya maneja hot-swapping de motores con liberación de VRAM
3. **Frontend** ya tiene selector de modelos (`MODELS` array) — solo agregar entrada
4. **`SongOrchestrator`** ya divide letras en secciones y delega al motor activo
5. **Docker** ya tiene la infraestructura GPU — solo agregar HeartMuLa al Dockerfile

### Archivos a crear/modificar:

```
backend/engines/heartmula_engine.py    ← NUEVO: Motor HeartMuLa
backend/engine_manager.py              ← MODIFICAR: Registrar HeartMuLa
backend/main.py                        ← MODIFICAR: Endpoint de generación HeartMuLa
backend/Dockerfile                     ← MODIFICAR: Instalar HeartMuLa + HeartCodec
frontend/src/App.jsx                   ← MODIFICAR: Agregar al selector de modelos
scripts/deploy_heartmula.py            ← NUEVO: Script de deploy
```

---

## 📝 Plan de Implementación (6 Pasos)

### PASO 1: Crear `backend/engines/heartmula_engine.py`
Motor que envuelve la inferencia de HeartMuLa siguiendo la interfaz `BaseEngine`:
- `load()`: Descarga checkpoints, carga HeartMuLa + HeartCodec
- `generate()`: Escribe lyrics/tags a archivos temporales, ejecuta inferencia
- `unload()`: Libera VRAM
- Soporte para `--lazy_load` en GPU única (RTX 5080 16GB)

### PASO 2: Registrar en `backend/engine_manager.py`
Agregar `"heartmula": HeartMuLaEngine` al diccionario `AVAILABLE_ENGINES`

### PASO 3: Actualizar `backend/main.py`
- Agregar endpoint de generación específico para HeartMuLa
- Manejar el flujo: lyrics + tags → archivo temporal → inferencia → audio
- Integrar con el pipeline de masterización existente

### PASO 4: Actualizar `backend/Dockerfile`
- Clonar `heartlib` repo
- Instalar dependencias de HeartMuLa
- Descargar checkpoints: HeartMuLa-oss-3B + HeartCodec-oss

### PASO 5: Actualizar `frontend/src/App.jsx`
- Agregar HeartMuLa al array `MODELS`
- Ajustar UI para mostrar tags además de lyrics

### PASO 6: Script de deploy
- `scripts/deploy_heartmula.py`: Deploy en caliente al servidor Madrid

---

## 🔧 Detalles Técnicos de HeartMuLa

### Checkpoints necesarios (HuggingFace):
```
./ckpt/
├── HeartCodec-oss/          ← HeartMuLa/HeartCodec-oss-20260123
├── HeartMuLa-oss-3B/        ← HeartMuLa/HeartMuLa-oss-3B-happy-new-year
├── gen_config.json          ← HeartMuLa/HeartMuLaGen
└── tokenizer.json           ← HeartMuLa/HeartMuLaGen
```

### Comando de inferencia:
```bash
python ./examples/run_music_generation.py \
  --model_path=./ckpt \
  --version="3B" \
  --lyrics=/tmp/lyrics.txt \
  --tags=/tmp/tags.txt \
  --save_path=/tmp/output.mp3 \
  --max_audio_length_ms=240000 \
  --topk=50 \
  --temperature=1.0 \
  --cfg_scale=1.5 \
  --lazy_load=true
```

### Formato de Tags (ejemplo):
```txt
genre: pop, mood: happy, instrument: piano, guitar, bpm: 120
```

### Formato de Lyrics (igual que YuE):
```txt
[Intro]

[Verse]
The sun creeps in across the floor
...

[Chorus]
...
```

### Parámetros clave:
| Parámetro | Default | Rango | Nota |
|---|---|---|---|
| `--max_audio_length_ms` | 240000 | 30000-300000 | Max 5 min |
| `--topk` | 50 | 10-100 | Calidad vs diversidad |
| `--temperature` | 1.0 | 0.5-1.5 | Creatividad |
| `--cfg_scale` | 1.5 | 1.0-3.0 | Adherencia al prompt |
| `--lazy_load` | false | true/false | Ahorro VRAM en GPU única |

---

## ⚡ Ventajas vs YuE

1. **3B vs 7B**: Menos VRAM, más rápido, mismo o mejor calidad
2. **HeartCodec**: Codec dedicado de 12.5Hz (vs xcodec problemático de YuE)
3. **Multilingual**: Soporte nativo para español, inglés, y muchos más
4. **Tags system**: Control fino del estilo musical
5. **Lazy loading**: Optimizado para GPU única como nuestra RTX 5080
6. **Comunidad activa**: 3,577⭐, ComfyUI nodes, Studio UI
7. **Roadmap**: 7B próximamente (comparable con Suno)
8. **Apache 2.0**: Uso comercial sin restricciones

---

## 🗓️ Timeline Estimado

| Paso | Duración | Dependencia |
|---|---|---|
| PASO 1: Engine | 1-2 horas | Ninguna |
| PASO 2: EngineManager | 15 min | PASO 1 |
| PASO 3: main.py | 1 hora | PASO 1-2 |
| PASO 4: Dockerfile | 30 min | PASO 1 |
| PASO 5: Frontend | 30 min | PASO 2 |
| PASO 6: Deploy script | 30 min | PASO 1-5 |
| **Total** | **~4-5 horas** | |

---

## 🎯 Próximos Pasos (Después de Integración)

1. **Benchmark A/B**: Generar misma canción con YuE vs HeartMuLa
2. **Ajuste de parámetros**: Optimizar temperature, cfg_scale, topk
3. **Tags auto-generation**: Usar Ollama para generar tags desde style_prompt
4. **HeartMuLa 7B**: Cuando se libere, actualizar (comparable con Suno)
5. **HeartTranscriptor**: Integrar para transcripción de audio existente
