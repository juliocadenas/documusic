# 🎯 Plan: Optimización YuE + Análisis Comparativo de Modelos

## Hallazgo Crítico (15 Mayo 2026)

**YuE SÍ genera vocales.** El test con el prompt oficial produjo una cantante femenina audible. El problema NO es el modelo — es la **configuración de inferencia y el post-procesado**.

### Diagnóstico de los problemas actuales

| Problema | Valor Actual | Valor Óptimo | Impacto |
|----------|-------------|--------------|---------|
| `max_new_tokens` | 1500 | 3000-6000 | Solo 15s de audio vs 30-60s |
| `run_n_segments` | 1 | 2-3 | Solo 1 sección de letra vs canción completa |
| Prompt genre | Tags complejos | Simple estilo oficial | El oficial funciona mejor |
| Mastering | loudnorm + limiter agresivo | Vocal-preserving EQ | Vocales enterradas en la mezcla |
| Cuantización | 16-bit (14GB VRAM) | 16-bit con OOM management | Ya correcto |

---

## 🔵 FASE 1: Optimización Inmediata de YuE

### 1.1 Simplificar prompt genre al estilo oficial

**Problema**: [`enrich_style_for_yue()`](backend/prompt_enricher.py:605) genera prompts como:
```
pop male singing bright vocal full vocal vocal uplifting emotional synth drums
```

**El oficial usa**:
```
inspiring female uplifting pop airy vocal electronic bright vocal vocal
```

**Cambios necesarios**:
- Reordenar: mood → gender → genre → timbre → vocal
- Agregar "inspiring" o "emotional" como primer tag (el oficial empieza con mood)
- Repetir "vocal" 2-3 veces al final (el oficial lo tiene 3 veces)
- Eliminar tags de instrumentos cuando no son necesarios (el oficial no tiene ninguno)
- Reducir total a ~6-8 tags (el oficial tiene 9)

**Archivo**: [`backend/prompt_enricher.py`](backend/prompt_enricher.py:605) — función `enrich_style_for_yue()`

### 1.2 Aumentar max_new_tokens progresivamente

**Restricción de VRAM**: RTX 5080 tiene 16GB. En 16-bit:
- Carga del modelo: ~14GB
- Stage 2 inference con max_new_tokens=1500: ~14.5GB peak
- OOM ocurrió con max_new_tokens=2000 en 8-bit

**Estrategia**: Test incremental en servidor
1. Probar max_new_tokens=3000 en 16-bit (debería caber: solo aumenta output, no modelo)
2. Si OOM → probar 2500
3. Si funciona → probar 4500
4. Documentar el límite real

**Archivo**: [`backend/main.py`](backend/main.py:497) — `YUE_PARAMS`

### 1.3 Aumentar run_n_segments

**Actual**: run_n_segments=1 → procesa solo 1 sección de letra
**Objetivo**: run_n_segments=2-3 → procesa 2-3 secciones (verse + chorus mínimo)

**Nota**: Cada segmento se procesa secuencialmente, no en paralelo. El VRAM peak es por segmento, no acumulativo. Pero el tiempo de inferencia aumenta linealmente.

**Estrategia**:
1. Primero aumentar max_new_tokens y verificar estabilidad
2. Luego aumentar run_n_segments a 2
3. Si estable → probar run_n_segments=3

**Archivo**: [`backend/main.py`](backend/main.py:497) — `YUE_PARAMS`

### 1.4 Crear pipeline de mastering que preserve vocales

**Problema actual**: [`master_audio_simple()`](backend/audio_master.py:168) aplica:
```
loudnorm=I=-14:TP=-1:LRA=11 → highpass=f=40 → alimiter=limit=0.95
```

Esto normaliza el volumen pero NO distingue entre vocal e instrumental. Si el instrumental es más fuerte, la normalización puede reducir las vocales.

**Pipeline propuesto**:
```
1. highpass=f=30 (remover solo sub-grave extremo)
2. equalizer=f=2500:t=o:w=2:g=2 (boost presencia vocal 2-4kHz)
3. equalizer=f=200:t=o:w=1:g=-1 (reducir boominess)
4. loudnorm=I=-14:TP=-1:LRA=11 (normalizar)
5. alimiter=limit=0.95 (protección)
6. afade (fade in/out suave)
```

**Alternativa avanzada**: Si tenemos acceso al vtrack e itrack por separado:
1. Boost vtrack +3dB antes de mezclar
2. Aplicar EQ vocal al vtrack
3. Mezclar vtrack + itrack
4. Masterizar el resultado

**Archivo**: [`backend/audio_master.py`](backend/audio_master.py:168) — función `master_audio_simple()` o nueva `master_audio_vocal_preserve()`

### 1.5 Script de test progresivo

Crear un script que teste automáticamente combinaciones de parámetros:

```
Test 1: max_new_tokens=3000, run_n_segments=1, prompt oficial
Test 2: max_new_tokens=3000, run_n_segments=2, prompt oficial
Test 3: max_new_tokens=4500, run_n_segments=2, prompt oficial
Test 4: max_new_tokens=3000, run_n_segments=3, prompt oficial
```

Para cada test: medir duración, VRAM peak, si hubo OOM, y calidad subjetiva.

**Archivo nuevo**: `scripts/test_yue_params.py`

---

## 🟡 FASE 2: Análisis Comparativo de Modelos

### 2.1 Modelos evaluados

| Modelo | Params | VRAM | Vocales | Calidad Instrumental | Licencia | Estado |
|--------|--------|------|---------|---------------------|----------|--------|
| **YuE 7B anneal-en-cot** | 7B | ~14GB (16-bit) | ✅ Sí (confirmado) | ⚠️ Media | Apache 2.0 | ✅ En uso |
| **ACE-Step v1-3.5B** | 3.5B | ~7GB | ❌ Pésima | ⚠️ Baja | Apache 2.0 | ❌ Descartado |
| **Stable Audio Open** | ~1B | ~4-7GB | ❌ No (solo instrumental) | ✅ Buena | Stability AI | 🔍 Por evaluar |
| **MusicGen Large** | 3.3B | ~6GB | ❌ No (solo instrumental) | ✅ Buena | MIT | 🔍 Por evaluar |
| **Bark** | ~1B | ~4GB | ✅ Sí (habla/canto básico) | ❌ No | MIT | 🔍 Por evaluar |

### 2.2 Estrategia YuE + Stable Audio Open (la "dupla")

```mermaid
flowchart LR
    A[Letra + Estilo] --> B[Stable Audio Open]
    A --> C[YuE 7B]
    B --> D[Instrumental Loop]
    D --> E[Audio Prompt]
    E --> C
    C --> F[Canción Completa con Vocales]
    F --> G[Post-procesado]
    G --> H[MP3 Final]
```

**Ventajas**:
- Stable Audio genera instrumentales con mejor textura sonora
- YuE "aprende" el ritmo del audio prompt y construye encima
- Resultado: mejor producción instrumental + vocales de YuE

**Desventajas**:
- Requiere 2 inferencias secuenciales (más tiempo)
- Stable Audio Open pesa ~7GB adicionales
- No caben ambos modelos en VRAM simultáneamente → hay que cargar/descargar

**VRAM Strategy**:
1. Cargar Stable Audio → generar loop → descargar
2. Cargar YuE → generar canción con audio prompt → descargar
3. Post-procesar

### 2.3 Evaluación honesta vs Suno AI

| Aspecto | YuE 7B Local | Suno AI v4 |
|---------|-------------|------------|
| **Calidad vocal** | ⚠️ Audible pero baja producción | ✅ Profesional, clara |
| **Coherencia musical** | ⚠️ Estructura básica | ✅ Compleja, profesional |
| **Duración** | ⚠️ 15-30s (limitado por VRAM) | ✅ Hasta 4 minutos |
| **Fidelidad al prompt** | ⚠️ Sigue letra pero no siempre estilo | ✅ Sigue letra y estilo |
| **Latencia** | ❌ 5-15 minutos | ✅ ~30 segundos |
| **Soberanía** | ✅ 100% local | ❌ Dependiente de API |
| **Costo** | ✅ Gratis (electricidad) | ❌ $10/mes mínimo |
| **Personalización** | ✅ Control total del audio | ❌ Lo que Suno entrega |

**Conclusión**: YuE NO alcanza nivel Suno en calidad, PERO puede mejorar significativamente con optimización. El objetivo realista es **calidad de demo profesional**, no nivel comercial.

---

## 🟢 FASE 3: Mejoras Avanzadas (Post-optimización)

### 3.1 Song Extender
- Tomar últimos N segundos de canción generada
- Usar como audio prompt para generar continuación
- Concatenar con crossfade
- Objetivo: canciones de 2-3 minutos

### 3.2 Separación y remezcla con UVR5
- Si YuE genera vocales pero con mala mezcla:
  1. Separar vocal/instrumental con UVR5
  2. Aplicar EQ/compresión independiente a cada pista
  3. Remezclar con balance profesional

### 3.3 Pipeline de audio prompt
- Generar instrumental en Stable Audio Open
- Usar como input para YuE
- YuE genera vocales sobre el instrumental

---

## 📋 Plan de Ejecución (Todo List)

### Prioridad 1 — Optimización YuE (inmediato)
1. [ ] Simplificar `enrich_style_for_yue()` al estilo del prompt oficial
2. [ ] Crear script de test progresivo de parámetros
3. [ ] Testear max_new_tokens=3000 en 16-bit (sin OOM)
4. [ ] Testear run_n_segments=2 con max_new_tokens=3000
5. [ ] Crear pipeline de mastering vocal-preserving
6. [ ] Deploy optimizaciones al servidor
7. [ ] Generar canción de prueba y evaluar calidad

### Prioridad 2 — Evaluación de modelos (después de P1)
8. [ ] Instalar y probar Stable Audio Open en servidor
9. [ ] Evaluar calidad instrumental de Stable Audio
10. [ ] Diseñar pipeline YuE + Stable Audio si vale la pena

### Prioridad 3 — Avanzado (después de P2)
11. [ ] Implementar song extender
12. [ ] Evaluar UVR5 para separación y remezcla
13. [ ] Pipeline de audio prompt completo
