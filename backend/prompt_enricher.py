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
