import os
# Requiere: pip install python-docx
import docx
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WordSongFactory:
    """
    Lee un archivo de Word masivo, extrae el título, estilo y letras de múltiples canciones,
    y prepara la estructura de datos para enviarla al Orquestador (GPU).
    """
    def __init__(self):
        pass

    def extract_songs_from_docx(self, file_path: str) -> list:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        doc = docx.Document(file_path)
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        
        # Asumimos una estructura en el Word usando marcadores:
        # [CANCIÓN: Titulo]
        # Estilo: Pop rock...
        # Letra:
        # verso 1...
        # [FIN CANCIÓN]
        
        song_blocks = re.findall(r'\[CANCIÓN:(.*?)\](.*?)\[FIN CANCIÓN\]', full_text, re.DOTALL | re.IGNORECASE)
        
        songs = []
        for title, content in song_blocks:
            title = title.strip()
            
            # Buscar el estilo
            style_match = re.search(r'Estilo:(.*?)(Letra:|$)', content, re.DOTALL | re.IGNORECASE)
            style = style_match.group(1).strip() if style_match else "Estilo genérico"
            
            # Buscar la letra
            lyrics_match = re.search(r'Letra:(.*)', content, re.DOTALL | re.IGNORECASE)
            lyrics = lyrics_match.group(1).strip() if lyrics_match else ""
            
            songs.append({
                "title": title,
                "style": style,
                "lyrics": lyrics
            })
            
        logger.info(f"Se extrajeron {len(songs)} canciones del archivo {file_path}")
        return songs

# factory = WordSongFactory()
# songs = factory.extract_songs_from_docx("canciones_masivas.docx")
