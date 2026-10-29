# Chain Punks Telegram Bot

A Telegram bot that returns Chain Punks ID cards by number or by matching uploaded artwork.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `python telegram-bot/run_bot.py` — build/resume the artwork index, then run the Telegram bot
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required project secrets: `TELEGRAM_BOT_TOKEN`, `ETH_RPC_URL`
- Python dependencies: `telegram-bot/requirements.txt`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

_Populate as you build — short repo map plus pointers to the source-of-truth file for DB schema, API contracts, theme files, etc._

## Architecture decisions

_Populate as you build — non-obvious choices a reader couldn't infer from the code (3-5 bullets)._

## Product

_Describe the high-level user-facing capabilities of this app once they exist._

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The first bot start indexes all 3,333 artwork images from Ethereum. The index is saved locally and resumed after interruptions.
- Telegram bot commands require the bot process to remain running.
- Card artwork and image fingerprints use Chromium to preserve embedded pixel glyphs. A renderer change bumps the index version and triggers a rebuild.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
