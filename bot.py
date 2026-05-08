
"""
bot.py — Telegram Video Watermark + Track Rename Bot (Pyrogram)
"""

import logging
import os
import tempfile
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, BOT_TOKEN, get_user_settings, set_user_settings, reset_user_settings
from processor import process_video_async

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

app = Client("watermark_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


def _settings_text(s: dict) -> str:
    return (
        "⚙️ **Your Current Settings**\n\n"
        f"📛 Channel name:   `{s['channel_name']}`\n"
        f"🖊️ Watermark text: `{s['watermark_text']}`\n\n"
        f"_Audio tracks_ → `{s['channel_name']} - Tamil`, `{s['channel_name']} - Hindi` _(etc.)_\n"
        f"_Subtitle tracks_ → `{s['channel_name']}`"
    )


@app.on_message(filters.command("start"))
async def cmd_start(client: Client, msg: Message):
    s = get_user_settings(msg.from_user.id)
    await msg.reply(
        "🎬 **Video Watermark + Track Rename Bot**\n\n"
        "Send me any video and I will:\n"
        "  ✅ Burn your text on screen _(first 10 seconds)_\n"
        "  ✅ Rename audio tracks → `@Channel - Language`\n"
        "  ✅ Rename subtitle tracks → `@Channel`\n\n"
        "📌 **Commands:**\n"
        "`/setname @YourChannel` — set channel name\n"
        "`/setwatermark Your text` — set watermark text\n"
        "`/settings` — view current settings\n"
        "`/reset` — reset to defaults\n\n"
        + _settings_text(s)
    )


@app.on_message(filters.command("help"))
async def cmd_help(client: Client, msg: Message):
    await msg.reply(
        "📖 **Help**\n\n"
        "`/setname @TechifyBots`\n"
        "→ Sets channel name used in track titles\n\n"
        "`/setwatermark Join @TechifyBots for more movies`\n"
        "→ Sets the text shown on video (0–10 sec)\n\n"
        "`/settings` → View your current settings\n"
        "`/reset` → Reset everything to defaults\n\n"
        "Then just **send any video** — I'll process it and send it back!"
    )


@app.on_message(filters.command("setname"))
async def cmd_setname(client: Client, msg: Message):
    args = msg.text.split(None, 1)
    if len(args) < 2:
        await msg.reply("Usage: `/setname @TechifyBots`")
        return
    channel_name = args[1].strip()
    set_user_settings(msg.from_user.id, channel_name=channel_name)
    await msg.reply(
        f"✅ Channel name set to: `{channel_name}`\n\n"
        f"Audio tracks → `{channel_name} - Tamil`, `{channel_name} - Hindi` _(etc.)_\n"
        f"Subtitle tracks → `{channel_name}`"
    )


@app.on_message(filters.command("setwatermark"))
async def cmd_setwatermark(client: Client, msg: Message):
    args = msg.text.split(None, 1)
    if len(args) < 2:
        await msg.reply("Usage: `/setwatermark Join @TechifyBots for more movies`")
        return
    watermark_text = args[1].strip()
    set_user_settings(msg.from_user.id, watermark_text=watermark_text)
    await msg.reply(
        f"✅ Watermark text set to:\n`{watermark_text}`\n\n"
        "This text will appear on screen for the first 10 seconds."
    )


@app.on_message(filters.command("settings"))
async def cmd_settings(client: Client, msg: Message):
    s = get_user_settings(msg.from_user.id)
    await msg.reply(_settings_text(s))


@app.on_message(filters.command("reset"))
async def cmd_reset(client: Client, msg: Message):
    s = reset_user_settings(msg.from_user.id)
    await msg.reply("🔄 Settings reset to defaults.\n\n" + _settings_text(s))


@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, msg: Message):
    file_obj = msg.video or msg.document
    if file_obj is None:
        return

    if msg.document:
        mime = msg.document.mime_type or ""
        if not mime.startswith("video/"):
            await msg.reply("Please send a video file.")
            return

    if file_obj.file_size and file_obj.file_size > MAX_FILE_SIZE:
        size_gb = file_obj.file_size / 1024 / 1024 / 1024
        await msg.reply(f"❌ File too large ({size_gb:.2f} GB). Max allowed: 2 GB.")
        return

    user_id        = msg.from_user.id
    s              = get_user_settings(user_id)
    channel_name   = s["channel_name"]
    watermark_text = s["watermark_text"]

    file_name = getattr(file_obj, "file_name", None) or "video.mkv"
    ext       = Path(file_name).suffix or ".mkv"

    status = await msg.reply("⏳ Downloading video… Please wait.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = str(Path(tmpdir) / f"input{ext}")
        output_path = str(Path(tmpdir) / f"output{ext}")

        try:
            last_pct = [-1]

            async def dl_progress(current, total):
                pct = int(current * 100 / total)
                if pct - last_pct[0] >= 10:
                    last_pct[0] = pct
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    try:
                        await status.edit(f"⬇️ Downloading...\n[{bar}] {pct}%")
                    except Exception:
                        pass

            await client.download_media(msg, file_name=input_path, progress=dl_progress)

            await status.edit("🔍 Detecting tracks + adding watermark…")

            result = await process_video_async(
                input_path, output_path, watermark_text, channel_name
            )

            last_pct[0] = -1

            async def ul_progress(current, total):
                pct = int(current * 100 / total)
                if pct - last_pct[0] >= 10:
                    last_pct[0] = pct
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    try:
                        await status.edit(f"⬆️ Uploading...\n[{bar}] {pct}%")
                    except Exception:
                        pass

            caption = f"✅ Done!\n\n🖊️ Watermark: `{watermark_text}`\n\n" + result["summary"]

            await client.send_document(
                chat_id=msg.chat.id,
                document=output_path,
                file_name=f"processed{ext}",
                caption=caption,
                progress=ul_progress,
            )

            await status.delete()

        except RuntimeError as exc:
            log.exception("Processing error")
            await status.edit(f"❌ Processing failed:\n`{exc}`")
        except Exception:
            log.exception("Unexpected error")
            await status.edit("❌ Something went wrong. Please try again.")


if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit("❌ Set BOT_TOKEN in config.py")
    if API_ID == "YOUR_API_ID" or API_HASH == "YOUR_API_HASH":
        raise SystemExit("❌ Set API_ID and API_HASH in config.py — get from https://my.telegram.org")

    log.info("Bot is running… Press Ctrl+C to stop.")
    app.run()
