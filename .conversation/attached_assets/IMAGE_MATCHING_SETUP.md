# Chain Punks Telegram bot: image matching update

This update lets the bot compare an uploaded artwork image with local fingerprints of the
3,333 Chain Punks images served by the contract. The image is processed in the bot; it is
not sent to an image-recognition service.

## Install and run

1. Copy the files in this bundle into the existing bot folder, keeping the filenames shown.
   Keep your existing `.env` file; do not replace it with `.env.example`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Build the artwork index once with `python build_index.py`. This needs a working
   `ETH_RPC_URL` in `.env` and makes one on-chain artwork request per punk. It can take a
   while. The script saves progress and can be rerun if the RPC provider rate-limits it.
4. Start the bot with `python bot.py`.
5. Send a clear punk artwork image. If the visual match is uncertain, send the punk number
   as the image caption instead.

`INDEX_WORKERS=1` in `.env` can help when an RPC provider applies strict rate limits.
The bot continues to support `/id 2889` and plain-number messages.
