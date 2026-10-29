"""Build or resume the local image-match index from on-chain Chain Punks art."""
import io
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv()

from chain import MAX_ID, fetch_art
from punkid import BrowserSvgRenderer
from punk_match import fingerprint, load_index, save_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("punkid.index")

INDEX_PATH = Path(__file__).with_name("punk_index.json")


def _fetch_art(token_id):
    """Fetch one on-chain SVG; retry transient RPC failures."""
    for attempt in range(3):
        try:
            return token_id, fetch_art(token_id)
        except Exception as exc:
            if attempt == 2:
                log.warning(
                    "Skipping punk %s after three RPC attempts (%s)",
                    token_id,
                    type(exc).__name__,
                )
                return token_id, None
            time.sleep(2 ** attempt)


def main():
    if not os.environ.get("ETH_RPC_URL"):
        raise SystemExit("Set ETH_RPC_URL in .env before building the image index.")

    fingerprints = load_index(INDEX_PATH)
    pending = [token_id for token_id in range(1, MAX_ID + 1) if token_id not in fingerprints]
    if not pending:
        log.info("Index is already complete: %s/%s artworks.", len(fingerprints), MAX_ID)
        return

    workers = max(1, min(4, int(os.environ.get("INDEX_WORKERS", "2"))))
    batch_size = max(1, workers * 8)
    log.info(
        "Indexing %s artworks (%s already saved), using %s worker(s). "
        "Chromium will render the embedded glyphs correctly.",
        len(pending),
        len(fingerprints),
        workers,
    )

    completed = 0
    with BrowserSvgRenderer() as renderer, ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            futures = [pool.submit(_fetch_art, token_id) for token_id in batch]
            for future in as_completed(futures):
                token_id, svg = future.result()
                if svg is not None:
                    try:
                        png = renderer.render(svg)
                        with Image.open(io.BytesIO(png)) as image:
                            fingerprints[token_id] = fingerprint(image)
                    except Exception as exc:
                        log.warning(
                            "Could not render punk %s (%s)",
                            token_id,
                            type(exc).__name__,
                        )
                completed += 1
                if completed % 25 == 0:
                    save_index(INDEX_PATH, fingerprints)
                    log.info(
                        "Processed %s/%s this run; indexed %s/%s artworks.",
                        completed,
                        len(pending),
                        len(fingerprints),
                        MAX_ID,
                    )

    save_index(INDEX_PATH, fingerprints)
    if len(fingerprints) == MAX_ID:
        log.info("Image index complete: %s/%s artworks.", len(fingerprints), MAX_ID)
    else:
        log.warning(
            "Index is incomplete: %s/%s artworks. Rerun this script to retry missing IDs.",
            len(fingerprints),
            MAX_ID,
        )


if __name__ == "__main__":
    main()
