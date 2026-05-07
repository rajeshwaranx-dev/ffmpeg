"""
processor.py — Orchestrates watermark + track rename in a single FFmpeg pass
"""

import asyncio
import logging
import subprocess
from pathlib import Path

from ffprobe_utils import get_tracks, format_track_summary
from watermark import build_drawtext_filter
from track_rename import build_track_metadata_args

log = logging.getLogger(__name__)


def _same_ext(input_path: str) -> str:
    """Return the same file extension as input (preserves .mkv, .mp4, etc.)"""
    return Path(input_path).suffix or ".mkv"


def process_video(
    input_path: str,
    output_path: str,
    watermark_text: str,
    channel_name: str,
) -> dict:
    """
    Single FFmpeg pass that:
      1. Burns watermark text on video (seconds 0–10)
      2. Renames all audio tracks → "{channel_name} - {Language}"
      3. Renames all subtitle tracks → "{channel_name}"

    Returns a result dict with track info and summary string.
    Raises RuntimeError if FFmpeg fails.
    """

    # ── Detect tracks ────────────────────────────────────────────────────────
    tracks          = get_tracks(input_path)
    audio_tracks    = tracks["audio"]
    subtitle_tracks = tracks["subtitle"]

    # ── Build FFmpeg filter & metadata args ──────────────────────────────────
    vf_filter   = build_drawtext_filter(watermark_text)
    metadata_args = build_track_metadata_args(audio_tracks, subtitle_tracks, channel_name)

    # ── Assemble FFmpeg command ───────────────────────────────────────────────
    # -map 0          → include ALL streams (video, audio, subtitles, attachments)
    # -c copy         → copy everything by default (fast)
    # -c:v libx264    → re-encode video only (needed to apply the drawtext filter)
    # -c:a copy       → keep audio untouched
    # -c:s copy       → keep subtitles untouched
    # -preset fast    → good speed/quality trade-off
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-map", "0",
        "-c:a", "copy",
        "-c:s", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        "-vf", vf_filter,
    ] + metadata_args + [output_path]

    log.info("FFmpeg command: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-1000:]}")

    summary = format_track_summary(tracks, channel_name)

    return {
        "audio_tracks":    audio_tracks,
        "subtitle_tracks": subtitle_tracks,
        "channel_name":    channel_name,
        "watermark_text":  watermark_text,
        "summary":         summary,
    }


async def process_video_async(
    input_path: str,
    output_path: str,
    watermark_text: str,
    channel_name: str,
) -> dict:
    """Async wrapper — runs FFmpeg in a thread so the bot stays responsive."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        process_video,
        input_path,
        output_path,
        watermark_text,
        channel_name,
    )
