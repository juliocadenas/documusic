"""
Song Orchestrator — Refactorizado para el sistema de motores intercambiables.
Delega la generación de audio al EngineManager, y se encarga de:
  - Dividir la letra en secciones
  - Ensamblar los segmentos con crossfade
  - Llevar el tracking de progreso
"""
import os
import logging
import uuid
from pydub import AudioSegment
from engine_manager import engine_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SongOrchestrator:

    def __init__(self, output_dir="generated_songs"):
        self.output_dir = output_dir
        self.progress = {}
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def parse_lyrics_into_sections(self, lyrics: str) -> list:
        """
        Divide la letra en secciones.
        - Primero intenta detectar marcadores explícitos: [Verse], [Chorus], [Bridge], etc.
        - Si no hay marcadores, divide por párrafos vacíos.
        """
        import re
        # Detectar bloques con marcadores tipo [Verse 1], [Chorus], [Bridge]
        pattern = r'(\[.+?\])'
        parts = re.split(pattern, lyrics)

        sections = []
        current_label = "Intro"
        current_text = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'\[.+?\]', part):
                # Es un marcador de sección
                if current_text.strip():
                    sections.append({"label": current_label, "text": current_text.strip()})
                current_label = part
                current_text = ""
            else:
                current_text += part + "\n"

        # Añadir la última sección
        if current_text.strip():
            sections.append({"label": current_label, "text": current_text.strip()})

        # Fallback: si no se detectaron marcadores, dividir por párrafos
        if not sections:
            raw_sections = [s.strip() for s in lyrics.split("\n\n") if s.strip()]
            sections = [{"label": f"Sección {i+1}", "text": s} for i, s in enumerate(raw_sections)]

        logger.info(f"Dividida la canción en {len(sections)} secciones: {[s['label'] for s in sections]}")
        return sections

    def combine_audio_segments(self, audio_files: list, final_filename: str) -> str:
        """Une segmentos WAV en un MP3 final con crossfade de 1 segundo."""
        if not audio_files:
            raise ValueError("No hay archivos de audio para combinar.")

        logger.info(f"Ensamblando {len(audio_files)} segmentos...")

        existing_files = [f for f in audio_files if os.path.exists(f)]
        if not existing_files:
            raise ValueError("Ningún archivo temporal encontrado.")

        combined = AudioSegment.from_wav(existing_files[0])
        for file in existing_files[1:]:
            next_segment = AudioSegment.from_wav(file)
            combined = combined.append(next_segment, crossfade=1000)

        output_path = os.path.join(self.output_dir, final_filename)
        combined.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"MP3 exportado: {output_path}")

        # Limpiar temporales
        for file in existing_files:
            try:
                os.remove(file)
            except Exception:
                pass

        return final_filename

    def process_song(self, song_title: str, style_prompt: str, lyrics: str, song_id: str = None) -> str:
        """
        Flujo principal de producción de una canción:
          1. Divide la letra en secciones.
          2. Para cada sección, llama al motor activo (YuE o ACE-Step).
          3. Ensambla todos los segmentos y exporta como MP3.
        """
        if not song_id:
            song_id = str(uuid.uuid4())

        active_engine = engine_manager.current_engine_name or "sin motor"
        self.progress[song_id] = {
            "title": song_title,
            "status": "starting",
            "percent": 0,
            "engine": active_engine,
        }

        try:
            # Verificar que hay un motor activo
            if not engine_manager.current_engine or not engine_manager.current_engine.is_loaded:
                raise RuntimeError(
                    "Ningún motor está cargado. Ve al panel y selecciona un motor antes de generar."
                )

            sections = self.parse_lyrics_into_sections(lyrics)
            temp_files = []
            total = len(sections)

            self.progress[song_id]["status"] = "generating_audio"
            self.progress[song_id]["total_sections"] = total

            for i, section in enumerate(sections):
                self.progress[song_id]["percent"] = int((i / total) * 90)
                self.progress[song_id]["current_section"] = section["label"]

                logger.info(f"[{active_engine}] Generando {section['label']} ({i+1}/{total})...")

                # Delegar al motor activo
                temp_wav = engine_manager.generate(
                    style_prompt=style_prompt,
                    lyrics=section["text"],
                    duration_seconds=60  # 1 minuto por sección por defecto
                )
                temp_files.append(temp_wav)

            self.progress[song_id]["status"] = "assembling"
            self.progress[song_id]["percent"] = 95

            final_name = f"{song_title.replace(' ', '_')}_{song_id[:6]}.mp3"
            self.combine_audio_segments(temp_files, final_name)

            self.progress[song_id]["status"] = "completed"
            self.progress[song_id]["percent"] = 100
            self.progress[song_id]["file_url"] = final_name

        except Exception as e:
            logger.error(f"Error en process_song [{song_id}]: {str(e)}")
            self.progress[song_id]["status"] = "error"
            self.progress[song_id]["message"] = str(e)

        return song_id

    def get_progress(self, song_id: str) -> dict:
        return self.progress.get(song_id, {"status": "not_found"})

    def get_all_songs(self) -> list:
        """Lista todas las canciones generadas en el directorio de salida."""
        songs = []
        for filename in os.listdir(self.output_dir):
            if filename.endswith(".mp3"):
                full_path = os.path.join(self.output_dir, filename)
                songs.append({
                    "filename": filename,
                    "size_mb": round(os.path.getsize(full_path) / (1024 * 1024), 2),
                    "url": f"/generated_songs/{filename}"
                })
        return sorted(songs, key=lambda x: x["filename"], reverse=True)


# Instancia global
orchestrator = SongOrchestrator()
