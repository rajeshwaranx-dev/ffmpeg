"""
watermark.py — Builds the FFmpeg drawtext filter string
"""

from config import (
    WATERMARK_FONT_SIZE,
    WATERMARK_FONT_COLOR,
    WATERMARK_BOX_COLOR,
    WATERMARK_BOX_ENABLED,
    WATERMARK_POSITION,
    WATERMARK_START_SEC,
    WATERMARK_END_SEC,
)

_POSITIONS = {
    "bottom_center": "x=(w-text_w)/2:y=h-th-20",
    "bottom_left":   "x=20:y=h-th-20",
    "top_center":    "x=(w-text_w)/2:y=20",
    "center":        "x=(w-text_w)/2:y=(h-text_h)/2",
}


def _escape(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    return (
        text
        .replace("\\", "\\\\")
        .replace("'",  "\\'")
        .replace(":",  "\\:")
    )


def build_drawtext_filter(watermark_text: str) -> str:
    """
    Returns the full FFmpeg -vf drawtext filter string.
    Text is only visible between WATERMARK_START_SEC and WATERMARK_END_SEC.
    """
    escaped  = _escape(watermark_text)
    xy       = _POSITIONS.get(WATERMARK_POSITION, _POSITIONS["bottom_center"])
    box_part = (
        f":box=1:boxcolor={WATERMARK_BOX_COLOR}:boxborderw=6"
        if WATERMARK_BOX_ENABLED else ""
    )

    return (
        f"drawtext=text='{escaped}'"
        f":fontsize={WATERMARK_FONT_SIZE}"
        f":fontcolor={WATERMARK_FONT_COLOR}"
        f"{box_part}"
        f":{xy}"
        f":enable='between(t,{WATERMARK_START_SEC},{WATERMARK_END_SEC})'"
    )
    
