#!/usr/bin/env python3
"""
Telegram Video Watermark Bot
-----------------------------
Send a video → bot adds your custom text watermark → returns the edited video.

Requirements:
    pip install python-telegram-bot==20.* aiofiles
    sudo apt install ffmpeg   (or: brew install ffmpeg)

Setup:
    1. Talk to @BotFather on Telegram → create a bot → copy the token.
    2. Set BOT_TOKEN below (or export as env var TELEGRAM_BOT_TOKEN).
    3. Customize WATERMARK_TEXT, FONT_SIZE, COLOR, POSITION as needed.
    4. Run: python telegram_watermark_bot.py
"""

import os
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8714275910:AAErRES-hHnDW7uZjpuFOVcdqzofKKP7nR4")

# Watermark text shown on the video
WATERMARK_TEXT = "Join Telegram channel for more movies - @yourchannel"

# FFmpeg drawtext options
FONT_SIZE   = 28          # px
FONT_COLOR  = "white"
BOX_COLOR   = "black@0.4" # semi-transparent background box
BOX_ENABLED = True        # set False to remove the background box

# Position: "bottom_center" | "bottom_left" | "top_center" | "center"
POSITION = "bottom_center"

# Max video size the bot will accept (bytes) – Telegram free limit is 20 MB
MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB (Bot API w/ local server)
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ── POSITION HELPER ──────────────────────────────────────────────────────────
def _drawtext_xy(position: str) -> str:
    positions = {
        "bottom_center": "x=(w-text_w)/2:y=h-th-20",
        "bottom_left":   "x=20:y=h-th-20",
        "top_center":    "x=(w-text_w)/2:y=20",
        "center":        "x=(w-text_w)/2:y=(h-text_h)/2",
    }
    return positions.get(position, positions["bottom_center"])


# ── FFMPEG WATERMARK ─────────────────────────────────────────────────────────
def add_watermark(input_path: str, output_path: str, text: str) -> None:
    """Burn text watermark into video using FFmpeg."""
    # Escape special characters for FFmpeg drawtext filter
    escaped = (
        text
        .replace("\\", "\\\\")
        .replace("'",  "\\'")
        .replace(":",  "\\:")
    )

    box_part = f":box=1:boxcolor={BOX_COLOR}:boxborderw=6" if BOX_ENABLED else ""
    xy       = _drawtext_xy(POSITION)

    # Text is visible only between START_SEC and END_SEC
    START_SEC = 0
    END_SEC   = 10

    vf_filter = (
        f"drawtext=text='{escaped}'"
        f":fontsize={FONT_SIZE}"
        f":fontcolor={FONT_COLOR}"
        f"{box_part}"
        f":{xy}"
        f":enable='between(t,{START_SEC},{END_SEC})'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-codec:a", "copy",   # keep original audio untouched
        "-preset", "fast",    # encoding speed vs size trade-off
        output_path,
    ]

    log.info("Running FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-500:]}")


# ── BOT HANDLERS ─────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎬 *Video Watermark Bot*\n\n"
        "Send me any video and I will burn this text onto it:\n"
        f"`{WATERMARK_TEXT}`\n\n"
        "Supported formats: MP4, MKV, AVI, MOV, etc.\n"
        f"Max size: {MAX_FILE_SIZE // 1024 // 1024} MB",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message

    # Accept both 'video' and 'document' (for files sent as files, not compressed)
    file_obj = msg.video or msg.document
    if file_obj is None:
        await msg.reply_text("Please send a video file.")
        return

    # Size check
    if file_obj.file_size and file_obj.file_size > MAX_FILE_SIZE:
        size_mb = file_obj.file_size / 1024 / 1024
        await msg.reply_text(
            f"❌ File too large ({size_mb:.1f} MB). "
            f"Max allowed: {MAX_FILE_SIZE // 1024 // 1024} MB."
        )
        return

    status = await msg.reply_text("⏳ Downloading video…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = str(Path(tmpdir) / "input.mp4")
        output_path = str(Path(tmpdir) / "output.mp4")

        try:
            # Download
            tg_file = await context.bot.get_file(file_obj.file_id)
            await tg_file.download_to_drive(input_path)
            log.info("Downloaded to %s", input_path)

            await status.edit_text("🖊️ Adding watermark…")

            # Process in executor so we don't block the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, add_watermark, input_path, output_path, WATERMARK_TEXT
            )

            await status.edit_text("📤 Uploading watermarked video…")

            with open(output_path, "rb") as f:
                await msg.reply_video(
                    video=f,
                    caption=f"✅ Watermark added:\n`{WATERMARK_TEXT}`",
                    parse_mode=constants.ParseMode.MARKDOWN,
                    supports_streaming=True,
                )

            await status.delete()

        except RuntimeError as exc:
            log.exception("Processing failed")
            await status.edit_text(f"❌ Processing failed:\n{exc}")
        except Exception:
            log.exception("Unexpected error")
            await status.edit_text("❌ Something went wrong. Please try again.")


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "I only process video files. Send a video and I'll watermark it! 🎬"
    )


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "❌  Set your bot token!\n"
            "    Edit BOT_TOKEN in the script, or:\n"
            "    export TELEGRAM_BOT_TOKEN='123456:ABC-...' && python telegram_watermark_bot.py"
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))

    # Videos sent compressed
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    # Videos/files sent as documents (uncompressed)
    app.add_handler(MessageHandler(filters.Document.VIDEO, handle_video))

    # Catch-all for anything else
    app.add_handler(MessageHandler(~filters.COMMAND, handle_unsupported))

    log.info("Bot is running… Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
