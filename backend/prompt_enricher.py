"""
Style Prompt Enricher for DocuMusic
Transforms short style descriptions like "American Country" into rich, detailed
prompts that describe instruments, vocals, tone, warmth, production quality, etc.
This makes YuE generate much more professional and varied output.
"""
import random
import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Genre Knowledge Base - Rich descriptions for each genre
# ============================================================
GENRE_PROFILES = {
    "country": {
        "instruments": [
            "acoustic guitar strumming", "fiddle melodies", "steel guitar slides",
            "banjo rolls", "upright bass", "mandolin accents", "dobro resonator",
            "pedal steel guitar", "harmonica fills", "twin fiddle harmonies"
        ],
        "vocals": [
            "warm male baritone vocal", "twangy female soprano", "close harmony duet",
            "nasal country vocal tone", "storytelling vocal delivery",
            "rich male vocal with Southern drawl", "sweet female alto with vibrato"
        ],
        "production": [
            "warm analog recording feel", "natural reverb", "tight rhythm section",
            "live studio performance feel", "crisp acoustic instruments",
            "Nashville sound production", "classic country mix"
        ],
        "mood": [
            "heartfelt", "nostalgic", "upbeat road-trip energy",
            "front porch storytelling", "honky-tonk swagger",
            "dusty road melancholy", "celebratory barn dance"
        ],
        "tempo": ["mid-tempo 120 BPM", "upbeat 140 BPM", "slow ballad 80 BPM", "driving 130 BPM"],
    },
    "rock": {
        "instruments": [
            "distorted electric guitar power chords", "crunchy guitar riffs",
            "pounding drum kit", "fuzzy bass guitar", "soaring guitar solo",
            "heavy crash cymbals", "palm-muted guitar chugs", "double kick drums",
            "feedback-drenched lead guitar", "thick wall of guitars"
        ],
        "vocals": [
            "powerful male rock vocal", "raw female rock vocal",
            "gritty vocal delivery", "soaring high notes",
            "raspy bluesy vocal tone", "anthemic group vocals",
            "intense passionate singing", "guttural rock growl"
        ],
        "production": [
            "big stadium rock sound", "punchy compression", "wide stereo guitars",
            "thunderous drum mix", "in-your-face vocal", "wall of sound production",
            "polished modern rock mix", "vintage tube amp warmth"
        ],
        "mood": [
            "explosive energy", "rebellious attitude", "epic and anthemic",
            "dark and brooding", "adrenaline-fueled", "emotional crescendo",
            "head-banging intensity"
        ],
        "tempo": ["driving 150 BPM", "mid-tempo rock 120 BPM", "fast punk 180 BPM", "slow heavy 90 BPM"],
    },
    "pop": {
        "instruments": [
            "synth pads", "programmed drum beats", "piano chords",
            "electric guitar clean picking", "bass synth", "string section",
            "electronic arpeggios", "acoustic guitar", "brass stabs",
            "glockenspiel sparkle", "layered synth hooks"
        ],
        "vocals": [
            "polished female pop vocal", "smooth male pop vocal",
            "breathy intimate vocal", "powerful belting chorus",
            "whispered verses", "vocal runs and melismas",
            "duet male and female harmonies", "catchy vocal hooks"
        ],
        "production": [
            "radio-ready mix", "sidechain compression", "sparkling highs",
            "punchy low end", "modern pop production", "layered vocal harmonies",
            "surgical EQ", "commercial sheen", "maximalist arrangement"
        ],
        "mood": [
            "upbeat and catchy", "dreamy atmospheric", "danceable groove",
            "emotional ballad", "feel-good summer vibes", "bittersweet nostalgia",
            "euphoric drop", "intimate late-night"
        ],
        "tempo": ["upbeat 128 BPM", "mid-tempo 110 BPM", "dance 140 BPM", "ballad 75 BPM"],
    },
    "jazz": {
        "instruments": [
            "smooth saxophone", "walking bass lines", "brushed snare drum",
            "grand piano improvisation", "muted trumpet", "vibraphone",
            "archtop jazz guitar", "ride cymbal swing", "double bass plucking",
            "trombone glissando", "B3 Hammond organ"
        ],
        "vocals": [
            "smooth jazz vocal", "scat singing", "smoky female contralto",
            "crooner male vocal", "laid-back vocal phrasing",
            "improvisational vocal runs", "warm intimate vocal tone"
        ],
        "production": [
            "intimate club recording", "warm tube microphone", "natural room acoustics",
            "minimal processing", "vintage jazz recording", "close-mic'd instruments",
            "spacious stereo image", "audiophile quality"
        ],
        "mood": [
            "late night smoky bar", "sophisticated elegance", "relaxed swing feel",
            "improvisational freedom", "melancholic blue note",
            "uptempo bebop energy", "cool West Coast vibes"
        ],
        "tempo": ["medium swing 130 BPM", "slow ballad 70 BPM", "fast bebop 200 BPM", "bossa nova 110 BPM"],
    },
    "latin": {
        "instruments": [
            "nylon string guitar", "congas and bongos", "trumpet fanfares",
            "timbales", "guiro scraper", "cowbell patterns", "tres guitar",
            "accordion", "marimba", "charango", "cajon percussion",
            "brass section stabs", "claves rhythm"
        ],
        "vocals": [
            "passionate male vocal", "sultry female vocal", "call and response coro",
            "Spanish guitar vocal style", "emotional passionate delivery",
            "rhythmic vocal syncopation", "harmonized coro section"
        ],
        "production": [
            "live band feel", "percussion-forward mix", "warm analog warmth",
            "danceable rhythm section", "bright brass production",
            "intimate acoustic setting", "fiesta energy"
        ],
        "mood": [
            "passionate and fiery", "romantic serenade", "danceable fiesta",
            "tropical paradise", "nostalgic bolero", "carnival celebration",
            "moonlit romance"
        ],
        "tempo": ["salsa 180 BPM", "bachata 120 BPM", "cumbia 100 BPM", "reggaeton 95 BPM"],
    },
    "electronic": {
        "instruments": [
            "analog synthesizer leads", "four-on-the-floor kick", "sidechained pads",
            "arpeggiated sequences", "filtered synth sweeps", "808 bass drops",
            "hi-hat patterns", "vocal chops", "granular textures",
            "modular synth bleeps", "reverb-drenched plucks"
        ],
        "vocals": [
            "ethereal female vocal", "processed robotic vocal", "whispered vocal hooks",
            "pitch-shifted vocal samples", "no vocal instrumental",
            "distant echoed vocal", "auto-tuned melodic vocal"
        ],
        "production": [
            "pristine digital mix", "deep sub-bass", "wide stereo imaging",
            "sidechain pumping", "multiband compression", "spatial audio",
            "mastered for clubs", "festival-ready drops"
        ],
        "mood": [
            "hypnotic trance", "dark underground", "euphoric build-up",
            "chill ambient vibes", "aggressive banger", "dreamy atmospheric",
            "peak-time dance floor"
        ],
        "tempo": ["128 BPM house", "140 BPM techno", "174 BPM drum and bass", "90 BPM chill"],
    },
    "rnb": {
        "instruments": [
            "smooth electric piano", "deep bass grooves", "programmed trap hi-hats",
            "silky guitar licks", "string pad harmonies", "808 kick patterns",
            " Rhodes piano chords", "vinyl crackle textures",
            "syncopated drum patterns", "organ chord stabs"
        ],
        "vocals": [
            "silky smooth R&B vocal", "soulful melismatic runs", "breathy intimate vocal",
            "powerful gospel-influenced belting", "layered vocal harmonies",
            "rap-sung flow", "whistle register notes", "call and response ad-libs"
        ],
        "production": [
            "warm analog mixing", "tight low end", "lush reverb on vocals",
            "vintage soul sampling feel", "modern trap-influenced drums",
            "polished contemporary R&B production", "intimate close-mic'd vocal"
        ],
        "mood": [
            "sensual and smooth", "late-night intimacy", "confident swagger",
            "heartbreak vulnerability", "groovy feel-good", "nostalgic 90s vibes",
            "modern sultry atmosphere"
        ],
        "tempo": ["slow jam 75 BPM", "mid-tempo groove 95 BPM", "uptempo R&B 115 BPM", "trap-soul 70 BPM"],
    },
    "folk": {
        "instruments": [
            "fingerpicked acoustic guitar", "cello bowing", "violin fiddle",
            "upright bass", "mandolin", "accordion", "tambourine",
            "harmonica", "dulcimer", "lap steel guitar", "hand percussion"
        ],
        "vocals": [
            "gentle folk vocal", "close harmony singing", "raw emotional vocal",
            "soft female vocal", "weathered male vocal", "whispered storytelling",
            "folk choir unison"
        ],
        "production": [
            "intimate bedroom recording", "natural acoustic space",
            "minimal overdubs", "warm analog tape feel", "live-off-the-floor",
            "wooden and organic sound", "gentle reverb"
        ],
        "mood": [
            "introspective and tender", "wanderlust adventure", "cozy campfire",
            "autumn melancholy", "hopeful morning", "pastoral serenity",
            "bittersweet storytelling"
        ],
        "tempo": ["gentle 90 BPM", "mid-tempo 110 BPM", "upbeat folk 130 BPM", "slow ballad 70 BPM"],
    },
    "hip-hop": {
        "instruments": [
            "808 bass", "boom bap drums", "sampled vinyl breaks", "scratching",
            "synth brass hits", "trap hi-hat rolls", "piano loop samples",
            "deep sub-bass", "orchestral stabs", "siren effects",
            "lo-fi chord progression"
        ],
        "vocals": [
            "hard-hitting rap flow", "melodic rap singing", "gang vocal hooks",
            "double-time verses", "spoken word interlude", "auto-tune crooning",
            "aggressive battle rap delivery", "laid-back West Coast flow"
        ],
        "production": [
            "hard-hitting drums", "sample-based production", "heavy 808 low end",
            "vinyl warmth and crackle", "modern trap production",
            "boom bap classic feel", "spacious reverb on melodic elements"
        ],
        "mood": [
            "hard and aggressive", "chill and laid-back", "street storytelling",
            "celebratory triumphant", "introspective conscious", "party anthem energy",
            "dark and atmospheric"
        ],
        "tempo": ["boom bap 90 BPM", "trap 140 BPM", "drill 145 BPM", "lo-fi 80 BPM"],
    },
    "cinematic": {
        "instruments": [
            "full orchestra strings", "epic brass section", "timpani drums",
            "choir voices", "piano ostinato", "French horn melodies",
            "suspended cymbal swells", "woodwind runs", "harp arpeggios",
            "synth bass pulse", "percussion ensemble"
        ],
        "vocals": [
            "soaring soprano solo", "dramatic choir", "ethereal vocalise",
            "whispered narration", "powerful tenor", "Gregorian chant"
        ],
        "production": [
            "Hollywood film score mix", "wide dynamic range", "spatial depth",
            "epic reverb tail", "IMAX-quality mastering", "orchestral hybrid production"
        ],
        "mood": [
            "epic and grandiose", "dark and ominous", "triumphant victory",
            "mysterious and enigmatic", "emotional crescendo", "tension and release",
            "awe-inspiring wonder"
        ],
        "tempo": ["slow building 70 BPM", "driving action 140 BPM", "epic march 100 BPM", "suspense 80 BPM"],
    },
}

# Keywords to detect genres from user input
GENRE_KEYWORDS = {
    "country": ["country", "americana", "bluegrass", "nashville", "honky", "western", "southern rock", "folk country"],
    "rock": ["rock", "rock and roll", "alternative", "indie rock", "punk", "metal", "grunge", "hard rock", "classic rock", "post-rock", "stoner"],
    "pop": ["pop", "pop rock", "indie pop", "synth pop", "k-pop", "j-pop", "electropop", "dream pop", "chamber pop", "art pop"],
    "jazz": ["jazz", "swing", "bebop", "bossa nova", "fusion", "smooth jazz", "cool jazz", "big band", "dixieland"],
    "latin": ["latin", "salsa", "bachata", "reggaeton", "cumbia", "merengue", "bossa", "samba", "tango", "ranchera", "bolero", "mambo", "spanish"],
    "electronic": ["electronic", "edm", "techno", "house", "trance", "dubstep", "ambient", "dnb", "drum and bass", "synthwave", "idm", "chillwave", "downtempo"],
    "rnb": ["rnb", "r&b", "soul", "neo-soul", "funk", "motown", "trap soul", "contemporary r&b"],
    "folk": ["folk", "acoustic", "singer-songwriter", "indie folk", "celtic", "bluegrass", "americana"],
    "hip-hop": ["hip hop", "hip-hop", "hiphop", "rap", "trap", "drill", "boom bap", "lo-fi hip hop", "lofi", "grime"],
    "cinematic": ["cinematic", "soundtrack", "film score", "orchestral", "epic", "trailer music", "game music", "classical"],
}

# Vocal gender/timbre modifiers
VOCAL_MODIFIERS = {
    "male": ["male vocal", "male voice", "baritone", "tenor", "male singer"],
    "female": ["female vocal", "female voice", "soprano", "alto", "female singer"],
    "duet": ["male and female duet", "duet harmonies", "alternating male female vocals"],
    "choir": ["choir", "group vocals", "gang vocals", "backing choir"],
    "instrumental": ["instrumental", "no vocals", "no vocal"],
}


def detect_genres(style_prompt: str) -> list:
    """Detect which genres are mentioned in the user's style prompt."""
    prompt_lower = style_prompt.lower()
    detected = []
    for genre, keywords in GENRE_KEYWORDS.items():
        for kw in keywords:
            if kw in prompt_lower:
                if genre not in detected:
                    detected.append(genre)
                break
    return detected if detected else ["pop"]  # Default to pop


def detect_vocal_preference(style_prompt: str) -> str | None:
    """Detect if user specified a vocal preference."""
    prompt_lower = style_prompt.lower()
    for pref, keywords in VOCAL_MODIFIERS.items():
        for kw in keywords:
            if kw in prompt_lower:
                return pref
    return None


def enrich_style_prompt(raw_prompt: str) -> str:
    """
    Transform a short style prompt into a rich, detailed description.
    
    Examples:
        "American Country" → "American Country, warm male baritone vocal, 
        acoustic guitar strumming, fiddle melodies, pedal steel guitar, 
        Nashville sound production, heartfelt storytelling, mid-tempo 120 BPM"
        
        "Rock ballad, female voice" → "Rock ballad, raw female rock vocal, 
        soaring guitar solo, piano chords, thunderous drum mix, 
        emotional crescendo, slow heavy 90 BPM"
    """
    if not raw_prompt or not raw_prompt.strip():
        raw_prompt = "pop rock"
    
    raw_prompt = raw_prompt.strip()
    
    # Detect genres and vocal preference
    genres = detect_genres(raw_prompt)
    vocal_pref = detect_vocal_preference(raw_prompt)
    
    # Build enriched prompt parts
    parts = [raw_prompt]  # Always start with the user's original input
    
    for genre in genres[:2]:  # Max 2 genres to avoid overcrowding
        profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["pop"])
        
        # Pick random elements from each category
        instruments = random.sample(
            profile["instruments"], 
            min(3, len(profile["instruments"]))
        )
        vocals = random.sample(
            profile["vocals"], 
            min(1, len(profile["vocals"]))
        )
        production = random.sample(
            profile["production"], 
            min(1, len(profile["production"]))
        )
        mood = random.sample(
            profile["mood"], 
            min(1, len(profile["mood"]))
        )
        tempo = random.sample(
            profile["tempo"], 
            min(1, len(profile["tempo"]))
        )
        
        # If user specified vocal preference, override the random vocal
        if vocal_pref and vocal_pref != "instrumental":
            vocal_overrides = {
                "male": [v for v in profile["vocals"] if "male" in v.lower() or "baritone" in v.lower() or "tenor" in v.lower()],
                "female": [v for v in profile["vocals"] if "female" in v.lower() or "soprano" in v.lower() or "alto" in v.lower()],
                "duet": [v for v in profile["vocals"] if "duet" in v.lower() or "harmon" in v.lower()],
                "choir": [v for v in profile["vocals"] if "choir" in v.lower() or "group" in v.lower() or "gang" in v.lower()],
            }
            override = vocal_overrides.get(vocal_pref, [])
            if override:
                vocals = [random.choice(override)]
        elif vocal_pref == "instrumental":
            vocals = ["instrumental only"]
        
        parts.extend(instruments)
        parts.extend(vocals)
        parts.extend(production)
        parts.extend(mood)
        parts.extend(tempo)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_parts = []
    for p in parts:
        p_lower = p.lower().strip()
        if p_lower not in seen:
            seen.add(p_lower)
            unique_parts.append(p.strip())
    
    enriched = ", ".join(unique_parts)
    
    # Truncate to max 80 chars (YuE file name limit)
    if len(enriched) > 80:
        # Smart truncation: keep the most important parts
        # Priority: original prompt + instruments + vocals
        essential = [raw_prompt]
        for genre in genres[:2]:
            profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["pop"])
            essential.extend(random.sample(profile["instruments"], min(2, len(profile["instruments"]))))
            essential.extend(random.sample(profile["vocals"], 1))
        
        enriched = ", ".join(essential)
        if len(enriched) > 80:
            # Hard truncate at last comma before 80
            truncated = enriched[:80]
            last_comma = truncated.rfind(',')
            if last_comma > 30:
                enriched = truncated[:last_comma].strip()
            else:
                enriched = truncated.strip()
    
    logger.info(f"[Enrich] '{raw_prompt}' → '{enriched}'")
    return enriched


# ============================================================
# YuE-specific tag enrichment — space-separated tags from known vocabulary
# ============================================================

# YuE known tags from top_200_tags.json — only these are valid for YuE genre.txt
YUE_KNOWN_TAGS = {
    # Genres (case-sensitive as in top_200_tags.json)
    "genres": {
        "country", "Country", "Bluegrass", "Americana", "country rock",
        "Crossover Country", "Rockabilly", "Folk", "folk", "Blues", "blues",
        "Rock", "rock", "Pop", "pop", "Jazz", "jazz", "R&B", "rnb",
        "Electronic", "electronic", "Hip Hop", "hip hop", "Rap", "rap",
        "Latin", "latin", "Reggae", "reggae", "Classical", "classical",
        "Metal", "metal", "Punk", "punk", "Soul", "soul", "Funk", "funk",
        "Gospel", "gospel", "Indie", "indie", "Alternative", "alternative",
        "Dance", "dance", "Disco", "disco", "Techno", "techno",
        "House", "house", "Ambient", "ambient", "Lo-Fi", "lo-fi",
        "Singer-Songwriter", "Singer-songwriter",
        "Cinematic", "cinematic", "Soundtrack", "soundtrack",
        "World Music", "world music", "Afrobeat", "afrobeat",
        "Bossa Nova", "bossa nova", "Salsa", "salsa",
        "Reggaeton", "reggaeton", "Bachata", "bachata",
        "Cumbia", "cumbia", "Samba", "samba",
    },
    # Instruments
    "instruments": {
        "guitar", "acoustic guitar", "electric guitar", "bass", "bass guitar",
        "drums", "piano", "keyboards", "synthesizer", "synth", "organ",
        "fiddle", "violin", "cello", "strings", "brass", "trumpet",
        "saxophone", "sax", "trombone", "flute", "clarinet",
        "banjo", "mandolin", "dobro", "pedal steel guitar", "steel guitar",
        "lap steel guitar", "harmonica", "accordion", "concertina",
        "ukulele", "uke", "harp", "xylophone", "vibraphone", "marimba",
        "congas", "bongos", "timbales", "percussion", "drum machine",
        "808", "808s", "turntable", "sampler",
    },
    # Vocal / voice tags
    "vocals": {
        "Vocal", "vocal", "Voice", "voice", "singing", "male vocal",
        "female vocal", "male voice", "female voice", "male", "female",
        "duet", "choir", "harmony", "harmonies", "a cappella",
        "falsetto", "whisper", "spoken word", "rap", "flow",
    },
    # Mood / descriptor tags
    "moods": {
        "inspiring", "uplifting", "airy", "bright", "warm", "dark",
        "melancholic", "melancholy", "happy", "sad", "energetic", "calm",
        "chill", "relaxed", "intense", "epic", "dreamy", "ethereal",
        "groovy", "funky", "smooth", "raw", "gritty", "soft", "gentle",
        "powerful", "emotional", "nostalgic", "romantic", "passionate",
        "aggressive", "haunting", "mysterious", "triumphant", "hopeful",
        "bittersweet", "atmospheric", "cinematic", "upbeat", "mellow",
    },
    # Production / quality tags
    "production": {
        "acoustic", "electric", "electronic", "analog", "digital",
        "live", "studio", "lo-fi", "hi-fi", "distorted", "clean",
        "reverb", "delay", "echo", "chorus", "compressed",
        "stripped-down", "minimal", "layered", "full band",
        "Nashville", "Motown", "classic", "modern", "vintage",
    },
}

# Mapping from user input keywords → YuE known tags
YUE_GENRE_MAP = {
    "country": ["country", "Country"],
    "americana": ["Americana"],
    "bluegrass": ["Bluegrass"],
    "nashville": ["country", "Nashville"],
    "western": ["country", "Country"],
    "honky": ["country", "Country"],
    "rock": ["Rock", "rock"],
    "rock and roll": ["Rock", "rock"],
    "alternative": ["Alternative"],
    "indie rock": ["Indie", "rock"],
    "punk": ["Punk", "punk"],
    "metal": ["Metal", "metal"],
    "grunge": ["Rock", "rock"],
    "hard rock": ["Rock", "rock"],
    "classic rock": ["Rock", "classic"],
    "pop": ["Pop", "pop"],
    "pop rock": ["Pop", "pop", "Rock"],
    "synth pop": ["Pop", "pop", "synth"],
    "indie pop": ["Pop", "pop", "Indie"],
    "k-pop": ["Pop", "pop"],
    "jazz": ["Jazz", "jazz"],
    "swing": ["Jazz", "jazz"],
    "bebop": ["Jazz", "jazz"],
    "bossa nova": ["Bossa Nova", "bossa nova", "Jazz"],
    "blues": ["Blues", "blues"],
    "rnb": ["R&B", "rnb", "soul"],
    "r&b": ["R&B", "rnb", "soul"],
    "soul": ["Soul", "soul"],
    "funk": ["Funk", "funk"],
    "electronic": ["Electronic", "electronic"],
    "edm": ["Electronic", "dance"],
    "techno": ["Techno", "techno"],
    "house": ["House", "house"],
    "trance": ["Electronic", "electronic"],
    "ambient": ["Ambient", "ambient"],
    "dubstep": ["Electronic", "electronic"],
    "synthwave": ["Electronic", "synth"],
    "hip hop": ["Hip Hop", "hip hop"],
    "hip-hop": ["Hip Hop", "hip hop"],
    "rap": ["Rap", "rap"],
    "trap": ["Hip Hop", "hip hop", "rap"],
    "latin": ["Latin", "latin"],
    "salsa": ["Salsa", "salsa", "Latin"],
    "bachata": ["Bachata", "bachata", "Latin"],
    "reggaeton": ["Reggaeton", "reggaeton", "Latin"],
    "cumbia": ["Cumbia", "cumbia", "Latin"],
    "samba": ["Samba", "samba", "Latin"],
    "folk": ["Folk", "folk", "acoustic"],
    "acoustic": ["Folk", "folk", "acoustic"],
    "singer-songwriter": ["Singer-Songwriter", "acoustic"],
    "cinematic": ["Cinematic", "cinematic"],
    "soundtrack": ["Soundtrack", "cinematic"],
    "orchestral": ["Classical", "classical", "cinematic"],
    "classical": ["Classical", "classical"],
    "reggae": ["Reggae", "reggae"],
    "gospel": ["Gospel", "gospel", "choir"],
    "disco": ["Disco", "disco", "dance"],
    "dance": ["Dance", "dance"],
    "lo-fi": ["Lo-Fi", "lo-fi"],
    "lofi": ["Lo-Fi", "lo-fi"],
    "world": ["World Music", "world music"],
    "afrobeat": ["Afrobeat", "afrobeat"],
}

# Instrument keyword → YuE known instrument tag
YUE_INSTRUMENT_MAP = {
    "guitar": "guitar",
    "acoustic guitar": "acoustic guitar",
    "electric guitar": "electric guitar",
    "steel guitar": "steel guitar",
    "pedal steel": "pedal steel guitar",
    "pedal steel guitar": "pedal steel guitar",
    "dobro": "dobro",
    "slide guitar": "steel guitar",
    "lap steel": "lap steel guitar",
    "banjo": "banjo",
    "mandolin": "mandolin",
    "fiddle": "fiddle",
    "violin": "violin",
    "cello": "cello",
    "strings": "strings",
    "piano": "piano",
    "keyboards": "keyboards",
    "synth": "synth",
    "synthesizer": "synthesizer",
    "organ": "organ",
    "bass": "bass",
    "bass guitar": "bass guitar",
    "drums": "drums",
    "drum": "drums",
    "harmonica": "harmonica",
    "accordion": "accordion",
    "trumpet": "trumpet",
    "saxophone": "saxophone",
    "sax": "sax",
    "trombone": "trombone",
    "flute": "flute",
    "harp": "harp",
    "ukulele": "ukulele",
    "percussion": "percussion",
    "congas": "congas",
    "bongos": "bongos",
    "brass": "brass",
    "808": "808",
    "drum machine": "drum machine",
}

# Mood keyword → YuE known mood tag
YUE_MOOD_MAP = {
    "inspiring": "inspiring", "inspirational": "inspiring",
    "uplifting": "uplifting", "upbeat": "upbeat",
    "airy": "airy", "bright": "bright",
    "warm": "warm", "dark": "dark",
    "melancholic": "melancholic", "melancholy": "melancholic", "sad": "sad",
    "happy": "happy", "energetic": "energetic",
    "calm": "calm", "chill": "chill", "relaxed": "relaxed",
    "intense": "intense", "epic": "epic",
    "dreamy": "dreamy", "ethereal": "ethereal",
    "groovy": "groovy", "funky": "funky",
    "smooth": "smooth", "raw": "raw", "gritty": "gritty",
    "soft": "soft", "gentle": "gentle",
    "powerful": "powerful", "emotional": "emotional",
    "nostalgic": "nostalgic", "romantic": "romantic",
    "passionate": "passionate", "aggressive": "aggressive",
    "haunting": "haunting", "mysterious": "mysterious",
    "triumphant": "triumphant", "hopeful": "hopeful",
    "bittersweet": "bittersweet", "atmospheric": "atmospheric",
    "mellow": "mellow",
}


def enrich_style_for_yue(raw_prompt: str) -> str:
    """
    Transform a style prompt into YuE-compatible space-separated tags.
    
    Follows the OFFICIAL YuE example pattern exactly:
        "inspiring female uplifting pop airy vocal electronic bright vocal vocal"
    
    Pattern: mood → gender → genre → timbre → "vocal" (repeated)
    
    Key principles (learned from testing):
    - Keep it SIMPLE: 6-9 tags max
    - NO instrument tags (official example has none)
    - ALWAYS repeat "vocal" 2-3 times at the end
    - Mood first (inspiring, emotional, uplifting)
    - Gender tag is critical (male/female)
    - Timbre tags: airy vocal, bright vocal, warm vocal, full vocal
    - Max ~80 chars
    """
    if not raw_prompt or not raw_prompt.strip():
        raw_prompt = "pop"
    
    raw_prompt = raw_prompt.strip()
    prompt_lower = raw_prompt.lower()
    
    tags = []  # Ordered list of tags to include
    seen = set()  # Track lowercase versions to avoid duplicates
    
    def _add_tag(tag: str):
        """Add a tag if not already present."""
        if tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    
    # Detect vocal preferences
    has_male = any(kw in prompt_lower for kw in ["male", "man", "baritone", "tenor", "boy"])
    has_female = any(kw in prompt_lower for kw in ["female", "woman", "soprano", "alto", "girl"])
    has_duet = any(kw in prompt_lower for kw in ["duet", "duo", "male and female", "both voices"])
    has_instrumental = any(kw in prompt_lower for kw in ["instrumental", "no vocal", "no vocals", "no voice"])
    
    # ===== OFFICIAL PATTERN: mood → gender → genre → timbre → vocal =====
    
    # 1. MOOD TAG (first, like official "inspiring")
    mood_added = False
    for mood_key, yue_tag in YUE_MOOD_MAP.items():
        if mood_key in prompt_lower:
            _add_tag(yue_tag)
            mood_added = True
            break  # Only ONE mood tag (official has just "inspiring")
    
    if not mood_added and not has_instrumental:
        _add_tag("inspiring")  # Official example starts with this
    
    # 2. GENDER TAG (second, like official "female")
    if not has_instrumental:
        if has_duet:
            _add_tag("female")
            _add_tag("male")
        elif has_female:
            _add_tag("female")
        elif has_male:
            _add_tag("male")
        else:
            _add_tag("female")  # Default to female (official example uses female)
    
    # 3. GENRE TAGS (like official "uplifting pop" / "electronic")
    genre_detected = False
    for genre_key, yue_tags in YUE_GENRE_MAP.items():
        if genre_key in prompt_lower:
            # Only add the first 1-2 genre tags (keep it simple)
            for t in yue_tags[:2]:
                _add_tag(t)
            genre_detected = True
            break  # Only match FIRST genre
    
    if not genre_detected:
        _add_tag("pop")
    
    # 4. TIMBRE TAGS (like official "airy vocal" / "bright vocal")
    if not has_instrumental:
        if has_female or (not has_male and not has_female):
            _add_tag("airy vocal")
            _add_tag("bright vocal")
        elif has_male:
            _add_tag("warm vocal")
            _add_tag("full vocal")
    
    # 5. ADD "vocal" REPEATED (official has it 3 times!)
    if not has_instrumental:
        _add_tag("vocal")
        _add_tag("vocal")
    
    # Build space-separated string
    result = " ".join(tags)
    
    # Enforce max 100 chars
    if len(result) > 100:
        # Priority: mood + gender + genre + timbre + vocal, drop extras
        while len(result) > 100 and len(tags) > 6:
            tags.pop()
            result = " ".join(tags)
    
    logger.info(f"[YuE Enrich] '{raw_prompt}' → '{result}' ({len(result)} chars, {len(tags)} tags)")
    return result


def get_enrichment_preview(raw_prompt: str) -> dict:
    """Get a preview of what the enrichment would produce (for frontend display)."""
    enriched = enrich_style_prompt(raw_prompt)
    genres = detect_genres(raw_prompt)
    vocal = detect_vocal_preference(raw_prompt)
    
    return {
        "original": raw_prompt,
        "enriched": enriched,
        "detected_genres": genres,
        "detected_vocal": vocal,
        "enriched_length": len(enriched),
    }


# ============================================================
# Lyrics Enrichment — Rule-based (no LLM)
# ============================================================

# Structural tags that indicate song sections
_SECTION_TAGS = re.compile(r'^\s*\[(Verse|Chorus|Bridge|Pre-Chorus|Outro|Intro|Hook|Refrain|Interlude|Solo)(?:\s*\d*)?\]\s*$', re.IGNORECASE)

# Common Spanish/English rhyme endings for simple phonetic matching
_RHYME_GROUPS_ES = {
    'ado': ['ado', 'ada', 'ados', 'adas'],
    'ido': ['ido', 'ida', 'idos', 'idas'],
    'ción': ['ción', 'sión', 'ción'],
    'dad': ['dad', 'dades'],
    'mente': ['mente'],
    'ón': ['ón', 'ones'],
    'ar': ['ar', 'arse', 'arte'],
    'er': ['er', 'erse', 'erte'],
    'ir': ['ir', 'irse', 'irte'],
    'al': ['al', 'ales'],
    'el': ['el', 'eles'],
    'il': ['il', 'iles'],
    'ol': ['ol', 'oles'],
    'ul': ['ul', 'ules'],
    'an': ['an', 'anes'],
    'en': ['en', 'enes'],
    'in': ['in', 'ines'],
    'on': ['on', 'ones'],
    'un': ['un', 'unes'],
    'or': ['or', 'ores'],
    'ez': ['ez', 'eces'],
    'uz': ['uz', 'uces'],
    'az': ['az', 'aces'],
    'iz': ['iz', 'ices'],
    'ar_': ['ar', 'ár'],
    'er_': ['er', 'ér'],
    'ir_': ['ir', 'ír'],
}

_RHYME_GROUPS_EN = {
    'ight': ['ight', 'ite', 'yte'],
    'ain': ['ain', 'ane', 'eign'],
    'ound': ['ound', 'owned'],
    'ing': ['ing', 'in\''],
    'tion': ['tion', 'sion'],
    'ness': ['ness'],
    'ful': ['ful', 'full'],
    'ly': ['ly', 'ley', 'lee'],
    'er': ['er', 'or', 'ur'],
    'ed': ['ed', 'd'],
    'es': ['es', 's'],
    'y': ['y', 'ie', 'ey'],
    'ow': ['ow', 'ough'],
    'oo': ['oo', 'ew', 'ue'],
    'ee': ['ee', 'ea', 'ie'],
    'ay': ['ay', 'ey', 'eigh'],
    'old': ['old', 'oled', 'ould'],
    'ore': ['ore', 'oar', 'our'],
}


def _normalize_text(text: str) -> str:
    """Remove accents and normalize for comparison."""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _get_rhyme_ending(word: str) -> str:
    """Get the rhyme-ending suffix of a word (last 2-4 chars for matching)."""
    word = word.strip().lower().rstrip('.,;:!?¡¿()"\'')
    if not word:
        return ''
    # Remove common suffixes to find the rhyme part
    if len(word) >= 4:
        return word[-3:]  # Last 3 chars is usually the rhyme
    elif len(word) >= 2:
        return word[-2:]
    return word


def _words_rhyme(w1: str, w2: str) -> bool:
    """Check if two words likely rhyme based on ending similarity."""
    e1 = _get_rhyme_ending(w1)
    e2 = _get_rhyme_ending(w2)
    if not e1 or not e2:
        return False
    # Direct match on last 2-3 chars
    if e1[-2:] == e2[-2:]:
        return True
    # Check known rhyme groups
    for group in [_RHYME_GROUPS_ES, _RHYME_GROUPS_EN]:
        for key, endings in group.items():
            if any(e1.endswith(e) for e in endings) and any(e2.endswith(e) for e in endings):
                return True
    return False


def _get_last_word(line: str) -> str:
    """Extract the last meaningful word from a line."""
    # Remove structural tags
    line = _SECTION_TAGS.sub('', line).strip()
    words = re.findall(r'[\wáéíóúüñÁÉÍÓÚÜÑ]+', line)
    return words[-1] if words else ''


def _split_into_sections(lyrics: str) -> list:
    """Split lyrics into sections based on blank lines or existing tags."""
    lines = lyrics.split('\n')
    sections = []
    current_section = []
    has_any_tag = any(_SECTION_TAGS.match(l) for l in lines)
    
    for line in lines:
        stripped = line.strip()
        
        # If line is a section tag, start new section
        if _SECTION_TAGS.match(stripped):
            if current_section:
                sections.append(current_section)
            current_section = [stripped]
        # Blank line = section separator (only if no tags exist)
        elif not stripped:
            if current_section and any(l.strip() for l in current_section):
                # Only split on blank lines if there are no tags at all
                if not has_any_tag:
                    sections.append(current_section)
                    current_section = []
                else:
                    current_section.append(line)
        else:
            current_section.append(line)
    
    if current_section:
        sections.append(current_section)
    
    return sections


def _section_text(section: list) -> str:
    """Get the text content of a section (excluding tags)."""
    return ' '.join(l.strip() for l in section if l.strip() and not _SECTION_TAGS.match(l.strip()))


def _sections_are_similar(s1_text: str, s2_text: str) -> bool:
    """Check if two sections are similar enough to be the same (chorus detection)."""
    # Normalize for comparison
    t1 = _normalize_text(s1_text)
    t2 = _normalize_text(s2_text)
    
    if not t1 or not t2:
        return False
    
    # Exact match
    if t1 == t2:
        return True
    
    # Check if one contains the other (partial chorus)
    if len(t1) > 20 and len(t2) > 20:
        if t1 in t2 or t2 in t1:
            return True
    
    # Word overlap ratio
    words1 = set(t1.split())
    words2 = set(t2.split())
    if not words1 or not words2:
        return False
    overlap = len(words1 & words2) / min(len(words1), len(words2))
    return overlap > 0.7


def _detect_chorus_sections(sections: list) -> set:
    """Detect which section indices are likely choruses based on repetition."""
    chorus_indices = set()
    section_texts = [_section_text(s) for s in sections]
    
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            if _sections_are_similar(section_texts[i], section_texts[j]):
                # Both are likely chorus if they repeat
                # The one with more text or appearing later is more likely chorus
                chorus_indices.add(i)
                chorus_indices.add(j)
    
    return chorus_indices


def enrich_lyrics_tags_only(raw_lyrics: str) -> str:
    """
    Add structural tags [Verse], [Chorus], [Bridge] to lyrics without changing the text.
    
    Strategy:
    - If lyrics already have tags, clean up formatting and return
    - Split by blank lines into sections
    - Detect choruses by repetition
    - Label remaining sections as verses/bridge
    """
    if not raw_lyrics or not raw_lyrics.strip():
        return raw_lyrics
    
    raw_lyrics = raw_lyrics.strip()
    
    # Check if lyrics already have structural tags
    existing_tags = _SECTION_TAGS.findall(raw_lyrics)
    if existing_tags:
        # Already has tags - just clean up spacing
        lines = raw_lyrics.split('\n')
        result = []
        for line in lines:
            stripped = line.strip()
            if _SECTION_TAGS.match(stripped):
                # Ensure blank line before tag (except at start)
                if result and result[-1].strip():
                    result.append('')
                result.append(stripped)
            else:
                result.append(line)
        return '\n'.join(result)
    
    # Split into sections
    sections = _split_into_sections(raw_lyrics)
    
    if len(sections) <= 1:
        # Single block - just label as [Verse]
        return f"[Verse]\n{raw_lyrics}"
    
    # Detect choruses
    chorus_indices = _detect_chorus_sections(sections)
    
    # Build tagged lyrics
    result_parts = []
    verse_count = 0
    chorus_count = 0
    
    for i, section in enumerate(sections):
        # Filter empty lines at start/end of section
        content_lines = []
        for l in section:
            if l.strip():
                content_lines.append(l)
        
        if not content_lines:
            continue
        
        # Determine tag
        if i in chorus_indices:
            if chorus_count == 0:
                tag = "[Chorus]"
            else:
                tag = "[Chorus]"  # Same tag for repeated choruses
            chorus_count += 1
        elif i == len(sections) - 1 and verse_count >= 2 and chorus_count >= 1:
            tag = "[Bridge]"
        else:
            verse_count += 1
            tag = f"[Verse {verse_count}]"
        
        section_text = '\n'.join(content_lines)
        result_parts.append(f"{tag}\n{section_text}")
    
    return '\n\n'.join(result_parts)


def _find_rhyme_suggestions(lines: list) -> dict:
    """
    Analyze lines and suggest rhyme improvements.
    Returns a dict mapping line_index -> suggested last word.
    """
    suggestions = {}
    last_words = [_get_last_word(line) for line in lines if line.strip() and not _SECTION_TAGS.match(line.strip())]
    content_line_indices = [i for i, line in enumerate(lines) if line.strip() and not _SECTION_TAGS.match(line.strip())]
    
    if len(last_words) < 2:
        return suggestions
    
    # Group consecutive pairs of lines (AABB pattern detection)
    for idx in range(0, len(content_line_indices) - 1, 2):
        i1 = content_line_indices[idx]
        i2 = content_line_indices[idx + 1] if idx + 1 < len(content_line_indices) else None
        if i2 is None:
            continue
        
        w1 = last_words[idx]
        w2 = last_words[idx + 1]
        
        if not _words_rhyme(w1, w2):
            # Try to find a rhyme for w1 that could replace w2
            # Simple approach: suggest swapping or noting non-rhyme
            # We don't change words automatically - just note the pattern
            pass
    
    return suggestions


def _improve_section(section_lines: list) -> list:
    """
    Improve a single section: better line breaks, consistent formatting,
    and basic flow improvements.
    """
    improved = []
    for line in section_lines:
        stripped = line.strip()
        
        # Keep tags as-is
        if _SECTION_TAGS.match(stripped):
            improved.append(stripped)
            continue
        
        # Clean up whitespace
        if not stripped:
            continue
        
        # Capitalize first letter of each line
        if stripped and stripped[0].islower():
            stripped = stripped[0].upper() + stripped[1:]
        
        # Remove trailing punctuation inconsistencies
        stripped = stripped.rstrip('.,;: ')
        # Add period or comma only if the line feels incomplete
        # (Don't force punctuation - let the user's style prevail)
        
        improved.append(stripped)
    
    return improved


def enrich_lyrics_improve(raw_lyrics: str) -> str:
    """
    Improve lyrics with better structure, tags, and basic flow improvements.
    Also adds structural tags like tags_only mode.
    
    Improvements:
    - Add [Verse]/[Chorus]/[Bridge] tags
    - Consistent capitalization
    - Clean up whitespace and formatting
    - Basic line grouping for better flow
    """
    if not raw_lyrics or not raw_lyrics.strip():
        return raw_lyrics
    
    raw_lyrics = raw_lyrics.strip()
    
    # First apply tags_only to get structure
    tagged = enrich_lyrics_tags_only(raw_lyrics)
    
    # Now improve each section
    sections = tagged.split('\n\n')
    improved_sections = []
    
    for section in sections:
        lines = section.split('\n')
        improved_lines = _improve_section(lines)
        
        if improved_lines:
            improved_sections.append('\n'.join(improved_lines))
    
    result = '\n\n'.join(improved_sections)
    
    # Add a subtle improvement note if we changed something
    # (The frontend can show this as a diff)
    return result


def get_lyrics_enrichment(raw_lyrics: str, mode: str) -> dict:
    """
    Enrich lyrics based on mode. Returns a dict with original and enriched text.
    
    Modes:
        'tags_only': Add [Verse]/[Chorus]/[Bridge] tags, keep text exact
        'improve': Add tags + improve formatting, capitalization, flow
    """
    if mode == 'tags_only':
        enriched = enrich_lyrics_tags_only(raw_lyrics)
    elif mode == 'improve':
        enriched = enrich_lyrics_improve(raw_lyrics)
    else:
        return {"error": f"Unknown mode: {mode}"}
    
    return {
        "original": raw_lyrics,
        "enriched": enriched,
        "mode": mode,
        "changed": enriched != raw_lyrics,
    }
