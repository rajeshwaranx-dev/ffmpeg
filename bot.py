"""
bot.py — Telegram Video Watermark + Track Rename Bot
------------------------------------------------------
Commands:
  /start         - Welcome message
  /setname       - Set channel name  (e.g. /setname @TechifyBots)
  /setwatermark  - Set custom watermark text  (e.g. /setwatermark Join us @TechifyBots)
  /settings      - Show your current settings
  /reset         - Reset settings to defaults
  /help          - Show help

Requirements:
  pip install "python-telegram-bot>=20"
  apt install ffmpeg

For 2 GB support:
  Run the local Bot API server first (see local_api_setup.sh)
  Then set:  export LOCAL_API_BASE_URL="http://localhost:8081/bot"
"""

import logging
import os
import tempfile
from pathlib import Path

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    LOCAL_API_BASE_URL,
    get_user_settings,
    reset_user_settings,
    set_user_settings,
)
from processor import process_video_async

# ── TOKEN ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── SIZE LIMIT ────────────────────────────────────────────────────────────────
# 2 GB requires LOCAL_API_BASE_URL to be set (local Bot API server).
# Without local server, Telegram enforces a 50 MB upload cap.
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024   # 2 GB

# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ── HELPER ────────────────────────────────────────────────────────────────────
def _settings_text(s: dict) -> str:
    return (
        "⚙️ *Your Current Settings*\n\n"
        f"📛 Channel name:   `{s['channel_name']}`\n"
        f"🖊️ Watermark text: `{s['watermark_text']}`\n\n"
        "_Audio tracks will be renamed to:_\n"
        f"`{s['channel_name']} - Tamil`\n"
        f"`{s['channel_name']} - Hindi`  _(etc. based on video)_\n\n"
        "_Subtitle tracks will be renamed to:_\n"
        f"`{s['channel_name']}`"
    )


# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = get_user_settings(update.effective_user.id)
    await update.message.reply_text(
        "🎬 *Video Watermark + Track Rename Bot*\n\n"
        "Send me any video and I will:\n"
        "  ✅ Burn your text on screen _(first 10 seconds)_\n"
        "  ✅ Rename audio tracks → `@Channel - Language`\n"
        "  ✅ Rename subtitle tracks → `@Channel`\n\n"
        "📌 *Commands:*\n"
        "`/setname @YourChannel` — set channel name\n"
        "`/setwatermark Your text` — set watermark text\n"
        "`/settings` — view current settings\n"
        "`/reset` — reset to defaults\n\n"
        + _settings_text(s),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Help*\n\n"
        "`/setname @TechifyBots`\n"
        "→ Sets channel name used in track titles and watermark\n\n"
        "`/setwatermark Join @TechifyBots for more movies`\n"
        "→ Sets the exact text shown on video (0–10 sec)\n\n"
        "`/settings` → View your current settings\n"
        "`/reset` → Reset everything to defaults\n\n"
        "Then just *send any video* — I'll process it and send it back!",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: `/setname @YourChannel`",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    channel_name = " ".join(context.args).strip()
    s = set_user_settings(update.effective_user.id, channel_name=channel_name)
    await update.message.reply_text(
        f"✅ Channel name set to: `{channel_name}`\n\n"
        f"Audio tracks will be renamed to:\n"
        f"`{channel_name} - Tamil`, `{channel_name} - Hindi` _(etc.)_\n\n"
        f"Subtitle tracks will be renamed to:\n"
        f"`{channel_name}`",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_setwatermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: `/setwatermark Join @YourChannel for more movies`",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    watermark_text = " ".join(context.args).strip()
    set_user_settings(update.effective_user.id, watermark_text=watermark_text)
    await update.message.reply_text(
        f"✅ Watermark text set to:\n`{watermark_text}`\n\n"
        "This text will appear on screen for the first 10 seconds.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = get_user_settings(update.effective_user.id)
    await update.message.reply_text(
        _settings_text(s),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = reset_user_settings(update.effective_user.id)
    await update.message.reply_text(
        "🔄 Settings reset to defaults.\n\n" + _settings_text(s),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ── VIDEO HANDLER ─────────────────────────────────────────────────────────────
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg      = update.message
    user_id  = update.effective_user.id

    # Accept video or document (uncompressed file)
    file_obj = msg.video or msg.document
    if file_obj is None:
        await msg.reply_text("Please send a video file.")
        return

    # Size check
    if file_obj.file_size and file_obj.file_size > MAX_FILE_SIZE:
        size_gb = file_obj.file_size / 1024 / 1024 / 1024
        await msg.reply_text(
            f"❌ File too large ({size_gb:.2f} GB). Max allowed: 2 GB."
        )
        return

    # Load this user's settings
    s              = get_user_settings(user_id)
    channel_name   = s["channel_name"]
    watermark_text = s["watermark_text"]

    status = await msg.reply_text("⏳ Downloading video… Please wait.")

    # Determine file extension
    file_name = getattr(file_obj, "file_name", None) or "video.mkv"
    ext       = Path(file_name).suffix or ".mkv"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = str(Path(tmpdir) / f"input{ext}")
        output_path = str(Path(tmpdir) / f"output{ext}")

        try:
            # Download
            tg_file = await context.bot.get_file(file_obj.file_id)
            await tg_file.download_to_drive(input_path)
            log.info("Downloaded: %s", input_path)

            await status.edit_text(
                "🔍 Detecting tracks…\n"
                "🖊️ Adding watermark + renaming tracks…"
            )

            # Process
            result = await process_video_async(
                input_path, output_path, watermark_text, channel_name
            )

            await status.edit_text("📤 Uploading processed video…")

            caption = (
                f"✅ Done!\n\n"
                f"🖊️ Watermark: `{watermark_text}`\n\n"
                + result["summary"]
            )

            with open(output_path, "rb") as f:
                await msg.reply_document(
                    document=f,
                    filename=f"processed{ext}",
                    caption=caption,
                    parse_mode=constants.ParseMode.MARKDOWN,
                )

            await status.delete()

        except RuntimeError as exc:
            log.exception("Processing error")
            await status.edit_text(f"❌ Processing failed:\n`{exc}`",
                                   parse_mode=constants.ParseMode.MARKDOWN)
        except Exception:
            log.exception("Unexpected error")
            await status.edit_text("❌ Something went wrong. Please try again.")


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a video file to process it. Type /help for commands."
    )


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "❌  Bot token not set!\n"
            "    export TELEGRAM_BOT_TOKEN='your_token_here'\n"
            "    or edit BOT_TOKEN in bot.py"
        )

    builder = Application.builder().token(BOT_TOKEN)

    if LOCAL_API_BASE_URL:
        builder = builder.base_url(LOCAL_API_BASE_URL)
        log.info("Using local Bot API server: %s", LOCAL_API_BASE_URL)
    else:
        log.warning(
            "LOCAL_API_BASE_URL not set — 2 GB support disabled. "
            "Files over 50 MB will fail."
        )

    app = builder.build()

    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("setname",      cmd_setname))
    app.add_handler(CommandHandler("setwatermark", cmd_setwatermark))
    app.add_handler(CommandHandler("settings",     cmd_settings))
    app.add_handler(CommandHandler("reset",        cmd_reset))

    app.add_handler(MessageHandler(filters.VIDEO,          handle_video))
    app.add_handler(MessageHandler(filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(~filters.COMMAND,       handle_unsupported))

    log.info("Bot is running… Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    
