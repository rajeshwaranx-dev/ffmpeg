"""
ffprobe_utils.py — Detect audio & subtitle tracks from video files
"""

import subprocess
import json
import logging

log = logging.getLogger(__name__)

# ISO 639-2 language code → readable name
LANG_MAP = {
    "tam": "Tamil",
    "tel": "Telugu",
    "hin": "Hindi",
    "eng": "English",
    "mal": "Malayalam",
    "kan": "Kannada",
    "ben": "Bengali",
    "mar": "Marathi",
    "pun": "Punjabi",
    "urd": "Urdu",
    "ara": "Arabic",
    "zho": "Chinese",
    "jpn": "Japanese",
    "kor": "Korean",
    "fre": "French",
    "spa": "Spanish",
    "ger": "German",
    "rus": "Russian",
    "und": "Unknown",
}


def _lang_to_name(lang_code: str) -> str:
    """Convert ISO 639-2 code to readable language name."""
    code = lang_code.lower().strip()
    if code in LANG_MAP:
        return LANG_MAP[code]
    # Fallback: capitalize the code itself
    return code.capitalize()


def get_tracks(file_path: str) -> dict:
    """
    Run ffprobe on file and return:
    {
        "audio":    [ { index, stream_index, lang_code, lang_name, existing_title }, ... ],
        "subtitle": [ { index, stream_index, lang_code, lang_name, existing_title }, ... ],
    }
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        file_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{result.stderr}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])

    audio_tracks    = []
    subtitle_tracks = []

    for s in streams:
        codec_type = s.get("codec_type", "")
        tags       = s.get("tags", {})
        lang_code  = tags.get("language", "und").lower()
        lang_name  = _lang_to_name(lang_code)
        existing_title = tags.get("title", "")

        entry = {
            "index":          s.get("index", 0),   # global stream index
            "lang_code":      lang_code,
            "lang_name":      lang_name,
            "existing_title": existing_title,
        }

        if codec_type == "audio":
            entry["stream_index"] = len(audio_tracks)   # 0-based audio-only index
            audio_tracks.append(entry)
        elif codec_type == "subtitle":
            entry["stream_index"] = len(subtitle_tracks)
            subtitle_tracks.append(entry)

    log.info(
        "Detected %d audio track(s), %d subtitle track(s)",
        len(audio_tracks), len(subtitle_tracks),
    )
    return {"audio": audio_tracks, "subtitle": subtitle_tracks}


def format_track_summary(tracks: dict, channel_name: str) -> str:
    """Return a human-readable summary of what will be renamed."""
    lines = ["📋 *Track Rename Preview:*\n"]

    if tracks["audio"]:
        lines.append("🔊 *Audio Tracks:*")
        for t in tracks["audio"]:
            old = t["existing_title"] or t["lang_name"]
            new = f"{channel_name} - {t['lang_name']}"
            lines.append(f"  `{old}` → `{new}`")
    else:
        lines.append("🔊 No audio tracks found.")

    lines.append("")

    if tracks["subtitle"]:
        lines.append("💬 *Subtitle Tracks:*")
        for t in tracks["subtitle"]:
            old = t["existing_title"] or t["lang_name"]
            new = channel_name
            lines.append(f"  `{old}` → `{new}`")
    else:
        lines.append("💬 No subtitle tracks found.")

    return "\n".join(lines)
    
