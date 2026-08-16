# Fridge Chef Bot (@Snap2MealBot)

Send photos of your fridge, get back what's inside — then (in later stages) recipes
with generated dish images and cooking instructions.

## Stage 1 (current)

- Telegram bot (`python-telegram-bot` v21, polling)
- Photo collection (up to 3 per session, largest resolution)
- Vision LLM (gpt-4o-mini) detects ingredients with confidence levels,
  plus "assumed staples" (oil, salt, pepper...)
- Structured output via Pydantic (`FridgeAnalysis`)

## Run

```bash
uv sync
uv run python -m fridge_chef.bot
```

Requires `.env` with `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, optional `VISION_MODEL`.

## Bot commands

- `/start` — new photo session + show remembered fridge
- send photos → `/done` — detect and **merge into persistent memory**
- `/fridge` — list remembered ingredients (✅✍️🤔❓ by source/confidence)
- `/add rice, soy sauce, 3 eggs` — add items manually
- `/remove eggs` · `/clear` — edit memory
- `/prefer vegetarian, no shrimp` — dietary preferences used in every recipe
- `/reset` — clear unanalyzed photos

## Evals

Measure detection quality on your own fridge photos:

```bash
# put photos in evals/photos/fridge_01.jpg with sidecar fridge_01.json:
# {"expected": ["eggs", "milk", "cabbage"]}
uv run python -m evals.run_eval
```

Rerun after any prompt/model change to catch regressions.

## Roadmap

- Stage 3: dish image generation per recipe / per step
- Later: cost caching, deployment (webhook + Docker)

## Storage

Fridge memory and preferences live in `data/fridge.db` (SQLite, auto-created).

## Workflow Example
<img width="503" height="124" alt="image" src="https://github.com/user-attachments/assets/4566b255-549f-4db5-8472-d2a7d3fbe2f2" />
<img width="536" height="705" alt="image" src="https://github.com/user-attachments/assets/506fb5d3-1b6e-4bc0-b977-b18388096a02" />
<img width="690" height="453" alt="image" src="https://github.com/user-attachments/assets/e95b57a3-361e-4e39-bb28-1fc874d7714c" />


