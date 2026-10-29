---
name: Telegram token log exposure
description: Preventing Bot API credentials from appearing in runtime logs.
---

Suppress HTTPX INFO request logs in the Telegram bot. The Bot API token is part of the request URL, and HTTPX logs that URL at INFO level.

**Why:** A startup log exposed the previous BotFather token, requiring the user to replace it.

**How to apply:** Keep the `httpx` logger at WARNING or higher. If a token is ever logged, stop the bot and have the user revoke it in BotFather before restarting with a replacement secret.
