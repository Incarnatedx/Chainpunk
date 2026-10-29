"""Telegram bot: send a punk number, get a Punk ID card back."""
import asyncio
import io
import logging
import os
import re
import time
from pathlib import Path

from PIL import Image
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chain import MAX_ID, fetch_punk
from punkid import make_card, svg_to_png
from punk_match import load_index, match_image

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
# httpx includes full Bot API request URLs in INFO logs; those URLs contain the token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("punkid.bot")

SHOW_HOLDER = os.environ.get("SHOW_HOLDER", "1") == "1"
COOLDOWN = 20          # seconds between requests per user
CACHE_TTL = 3600       # seconds to keep a punk's data (the holder can change)
_cache = {}            # token_id -> (time, png bytes)
_last = {}             # user_id -> time of last request
_gate = asyncio.Semaphore(2)  # at most 2 chain lookups at once

HELP = (
    "Send me a Chain Punk image and I'll try to identify it and make its Punk ID card "
    "(image matching must be indexed first). You can also send a number (1-3333).\n\n"
    "Examples:\n/id 2889\nor just: 2889\n\n"
    "For a photo, add the number as its caption to skip visual matching. "
    "If the image match is uncertain, I'll ask for the number instead.\n\n"
    "Fan-made, not official. The art is CC0."
)
INDEX_PATH = Path(__file__).with_name("punk_index.json")
_index_mtime = None
_index_cache = None


def build_card_png(token_id):
    data, svg = fetch_punk(token_id)
    art = Image.open(io.BytesIO(svg_to_png(svg)))
    card = make_card(art, data, show_holder=SHOW_HOLDER)
    out = io.BytesIO()
    card.save(out, format="PNG")
    return out.getvalue()


async def respond(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    token_id: int,
    caption: str = None,
):
    msg = update.effective_message
    if not 1 <= token_id <= MAX_ID:
        await msg.reply_text(f"Punk numbers go from 1 to {MAX_ID}.")
        return

    user = update.effective_user.id
    wait = COOLDOWN - (time.time() - _last.get(user, 0))
    if wait > 0:
        await msg.reply_text(f"Easy there, try again in {int(wait) + 1}s.")
        return
    _last[user] = time.time()

    cached = _cache.get(token_id)
    if cached and time.time() - cached[0] < CACHE_TTL:
        png = cached[1]
    else:
        await context.bot.send_chat_action(msg.chat_id, ChatAction.UPLOAD_PHOTO)
        try:
            async with _gate:
                png = await asyncio.to_thread(build_card_png, token_id)
        except Exception as exc:
            log.error("failed for punk %s (%s)", token_id, type(exc).__name__)
            await msg.reply_text("Couldn't read that punk right now. Try again in a minute.")
            return
        _cache[token_id] = (time.time(), png)

    await msg.reply_photo(
        photo=io.BytesIO(png),
        caption=caption or f"Punk ID #{token_id}",
    )


def find_number(text):
    m = re.search(r"\d{1,4}", text or "")
    return int(m.group()) if m else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = find_number(" ".join(context.args))
    if n is None:
        await update.effective_message.reply_text("Send a number, like /id 2889")
        return
    await respond(update, context, n)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = find_number(update.effective_message.text)
    if n is None:
        await update.effective_message.reply_text(HELP)
        return
    await respond(update, context, n)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    n = find_number(msg.caption)
    if n is None:
        index = _get_index()
        if index is None:
            await msg.reply_text(
                "Image matching isn't set up yet. In the bot folder, run "
                "`python build_index.py` once with ETH_RPC_URL configured, then restart the bot. "
                "For now, add the punk number as the photo caption (for example, 2889).",
                parse_mode="Markdown",
            )
            return
        if len(index) < MAX_ID:
            await msg.reply_text(
                f"The artwork index is incomplete ({len(index)}/{MAX_ID}). "
                "Finish or rerun `python build_index.py`, then restart the bot.",
                parse_mode="Markdown",
            )
            return
        try:
            photo = msg.photo[-1]
            telegram_file = await context.bot.get_file(photo.file_id)
            photo_bytes = bytes(await telegram_file.download_as_bytearray())
            result = match_image(photo_bytes, index)
        except Exception as exc:
            log.error("could not process photo (%s)", type(exc).__name__)
            await msg.reply_text(
                "I couldn't process that image. Try a clear crop of the punk artwork, "
                "or add its number as the caption."
            )
            return

        if result["status"] == "match":
            n = result["token_id"]
            await respond(
                update,
                context,
                n,
                caption=f"Likely image match · Punk ID #{n}",
            )
            return
        if result["status"] == "ambiguous":
            await msg.reply_text(
                "I found similar artwork but can't choose the ID confidently. "
                "Add the punk number as the photo caption, or send `/id 2889`."
            )
            return
        await msg.reply_text(
            "I couldn't match that image confidently. Try a clear crop of the punk artwork, "
            "or add its number as the photo caption."
        )
        return
    await respond(update, context, n)


def _get_index():
    """Load the completed fingerprint index and refresh it if the file changes."""
    global _index_mtime, _index_cache
    try:
        mtime = INDEX_PATH.stat().st_mtime
    except FileNotFoundError:
        return None
    if _index_cache is None or mtime != _index_mtime:
        try:
            _index_cache = load_index(INDEX_PATH)
            _index_mtime = mtime
        except (OSError, ValueError):
            log.error("artwork index is unreadable or has an unsupported version")
            return None
    return _index_cache


def main():
    app = (
        Application.builder()
        .token(os.environ["TELEGRAM_BOT_TOKEN"])
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(10)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    # Keep retrying transient Telegram API timeouts during startup.
    app.run_polling(bootstrap_retries=-1)


if __name__ == "__main__":
    main()
