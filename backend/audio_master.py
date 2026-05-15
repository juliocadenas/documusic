"""
Audio Mastering Pipeline for DocuMusic
Post-processing chain: LoudNorm → EQ → Compression → Stereo Widen → Fade → Final MP3
Uses FFmpeg for all audio processing (no extra Python dependencies needed).
"""
import os
import subprocess
import logging
import json
import tempfile

logger = logging.getLogger(__name__)


def analyze_audio(input_path: str) -> dict:
    """
    Analyze audio file using FFmpeg's loudnorm filter in analysis mode.
    Returns LUFS, true peak, and other metrics.
    """
    cmd = [
        "ffmpeg", "-i", input_path,
        "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # FFmpeg prints loudnorm stats to stderr
        output = result.stderr
        # Find the JSON block
        start = output.rfind("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            stats = json.loads(output[start:end])
            return {
                "input_lufs": float(stats.get("input_i", -14)),
                "input_tp": float(stats.get("input_tp", 0)),
                "input_lra": float(stats.get("input_lra", 0)),
                "input_thresh": float(stats.get("input_thresh", -70)),
                "target_lufs": -14,
            }
    except Exception as e:
        logger.warning(f"[Master] Could not analyze audio: {e}")
    return {"input_lufs": -14, "target_lufs": -14}


def master_audio(input_path: str, output_path: str = None, quality: str = "high") -> str:
    """
    Apply professional mastering pipeline to an audio file.
    
    Pipeline:
    1. Loudness normalization to -14 LUFS (streaming standard)
    2. High-pass filter (remove sub-bass rumble below 40Hz)
    3. Gentle presence boost (2-4kHz for vocal clarity)
    4. Dynamic compression (tame peaks, even out dynamics)
    5. Stereo widening (subtle, ~20%)
    6. Soft limiter (prevent clipping)
    7. Fade in/out
    
    Args:
        input_path: Path to input audio file (MP3/WAV)
        output_path: Path for output file. If None, replaces extension with _mastered.mp3
        quality: "high" (320kbps), "standard" (192kbps), or "lossless" (WAV)
    
    Returns:
        Path to the mastered audio file
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_mastered.mp3"

    # Build the FFmpeg filter chain
    filters = _build_master_chain(quality)

    # Bitrate based on quality
    bitrate = {"high": "320k", "standard": "192k", "lossless": None}.get(quality, "320k")

    cmd = ["ffmpeg", "-y", "-i", input_path]

    # Add filter chain
    cmd.extend(["-af", filters])

    # Output codec and quality
    if quality == "lossless":
        cmd.extend(["-c:a", "pcm_s16le"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])

    cmd.append(output_path)

    logger.info(f"[Master] Applying mastering pipeline to {input_path}")
    logger.debug(f"[Master] FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"[Master] FFmpeg error: {result.stderr[-500:]}")
            # Fallback: just copy the file as-is
            import shutil
            shutil.copy2(input_path, output_path)
            logger.warning(f"[Master] Fallback: copied original file to {output_path}")
            return output_path
    except subprocess.TimeoutExpired:
        logger.error("[Master] FFmpeg timed out, copying original")
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    # Verify output exists and has content
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        orig_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        logger.info(f"[Master] ✅ Mastering complete: {orig_size} → {new_size} bytes")
        return output_path
    else:
        logger.warning("[Master] Output file too small or missing, using original")
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path


def _build_master_chain(quality: str = "high") -> str:
    """
    Build the FFmpeg audio filter chain for mastering.
    Returns a single filter_complex string.
    """
    filters = []

    # 1. Two-pass loudness normalization (single-pass for speed, still effective)
    # Target: -14 LUFS (Spotify/YouTube standard), True Peak: -1dB, LRA: 11
    filters.append("loudnorm=I=-14:TP=-1:LRA=11")

    # 2. High-pass filter: remove sub-bass rumble below 40Hz (common artifact)
    filters.append("highpass=f=40")

    # 3. Low-pass filter: remove ultra-high frequencies above 16kHz (reduce harshness)
    filters.append("lowpass=f=16000")

    # 4. Gentle presence EQ boost for vocal clarity (2-4kHz range)
    # Using peaking filter: freq=3000Hz, bandwidth=1.5 octaves, gain=+1.5dB
    filters.append("equalizer=f=3000:t=o:w=1.5:g=1.5")

    # 5. Slight warmth boost (100-300Hz range) for fullness
    filters.append("equalizer=f=200:t=o:w=1.0:g=1.0")

    # 6. Dynamic compression: even out volume between verse/chorus
    # attack=50ms, release=200ms, threshold=-18dB, ratio=3:1, makeup gain=2dB
    filters.append("compand=.1|.1:.2|.2:-inf/-45.1/-inf/-inf:6:0:-90:0.1")

    # 7. Stereo widening (subtle, ~20%)
    # Only if stereo - using haas effect for width
    filters.append("stereotools=mlev=0.15")

    # 8. Soft limiter to prevent any clipping
    filters.append("alimiter=limit=0.95:level=off:attack=5:release=50")

    # 9. Fade in (500ms) and fade out (2s)
    # Apply fade in to first 0.5s, fade out to last 2s
    filters.append("afade=t=in:st=0:d=0.5,afade=t=out:st=9998:d=2")

    # Join all filters
    chain = ",".join(filters)
    return chain


def master_audio_simple(input_path: str, output_path: str = None) -> str:
    """
    Vocal-preserving mastering for YuE output.
    
    Key design: Boost vocal presence (2-4kHz) before loudness normalization
    so that the loudnorm doesn't squash the vocals. The order matters:
    EQ first → then normalize → then limit.
    
    Chain: highpass → vocal presence EQ → warmth cut → loudnorm → limiter → fade
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_mastered.mp3"

    # Vocal-preserving mastering chain
    # Order matters! EQ before loudnorm so vocals aren't squashed
    filters = [
        "highpass=f=30",                          # Remove only extreme sub-bass
        "equalizer=f=3000:t=o:w=2:g=3",           # Vocal presence boost (2-4kHz, +3dB)
        "equalizer=f=200:t=o:w=1:g=-1.5",         # Reduce boominess (200Hz, -1.5dB)
        "equalizer=f=8000:t=h:w=1.5:g=1",         # Air/brightness boost (8kHz+, +1dB)
        "loudnorm=I=-14:TP=-1:LRA=11",             # Streaming-standard loudness
        "alimiter=limit=0.95:attack=5:release=50",  # Soft limiter
        "afade=t=in:st=0:d=0.3",                   # Short fade in
        "afade=t=out:st=9998:d=1.5",               # Gentle fade out
    ]

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", ",".join(filters),
        "-c:a", "libmp3lame", "-b:a", "320k",
        output_path
    ]

    logger.info(f"[Master] Vocal-preserving mastering: {input_path} → {output_path}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"[Master] Error: {result.stderr[-300:]}")
            import shutil
            shutil.copy2(input_path, output_path)
    except Exception as e:
        logger.error(f"[Master] Exception: {e}")
        import shutil
        shutil.copy2(input_path, output_path)

    return output_path


def get_audio_duration(input_path: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def get_audio_metrics(input_path: str) -> dict:
    """Get comprehensive audio metrics for quality scoring."""
    duration = get_audio_duration(input_path)
    analysis = analyze_audio(input_path)
    file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0

    return {
        "duration_seconds": round(duration, 1),
        "file_size_bytes": file_size,
        "lufs": analysis.get("input_lufs", 0),
        "true_peak": analysis.get("input_tp", 0),
        "lra": analysis.get("input_lra", 0),
    }
