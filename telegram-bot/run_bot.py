"""Build the art index once when needed, then start Telegram polling."""
import logging
import os
from threading import Thread

from bot import main as run_polling
from build_index import INDEX_PATH, main as build_index
from chain import MAX_ID
from punk_match import load_index

log = logging.getLogger("punkid.runner")


def main():
    missing = [
        key
        for key in ("TELEGRAM_BOT_TOKEN", "ETH_RPC_URL")
        if not os.environ.get(key)
    ]
    if missing:
        raise SystemExit(
            "Add these project secrets before starting the bot: " + ", ".join(missing)
        )

    try:
        indexed = len(load_index(INDEX_PATH))
    except (OSError, ValueError):
        indexed = 0

    if indexed < MAX_ID:
        log.info("Artwork index has %s/%s entries; building or resuming it.", indexed, MAX_ID)
        Thread(
            target=build_index,
            name="punk-art-indexer",
            daemon=True,
        ).start()

    run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
