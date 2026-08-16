"""Fridge Chef bot — Stages 1, 2 and 4.

Photos -> ingredient detection -> persistent fridge memory -> recipes with
dietary preferences. Run with: uv run python -m fridge_chef.bot
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import config, store
from .recipes import format_recipe, generate_recipes
from .vision import analyze_fridge_photos

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger("fridge_chef")

MAX_PHOTOS = 3
ICONS = {"high": "✅", "medium": "🤔", "low": "❓", "manual": "✍️"}


def fridge_text(user_id: int) -> str:
    items = store.get_fridge(user_id)
    if not items:
        return "Your fridge is empty — send photos or use /add."
    lines = [f"🥗 *Your fridge ({len(items)} items):*\n"]
    for item in items:
        qty = f" — {item.quantity}" if item.quantity else ""
        lines.append(f"{ICONS.get(item.confidence, '•')} {item.name}{qty}")
    prefs = store.get_preference(user_id)
    if prefs:
        lines.append(f"\n⚠️ Preferences: {prefs}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data["photos"] = []
    text = (
        "👋 I'm Fridge Chef. Send 1-3 fridge photos, then /done to analyze.\n\n"
        f"{fridge_text(update.effective_user.id)}\n\n"
        "Commands: /fridge · /add · /remove · /clear · /prefer · /done · /help"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def fridge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(fridge_text(update.effective_user.id), parse_mode="Markdown")


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """e.g. /add rice, soy sauce, 3 onions"""
    if not context.args:
        await update.message.reply_text("Usage: /add rice, soy sauce, 3 onions")
        return
    user_id = update.effective_user.id
    for raw in " ".join(context.args).split(","):
        name = raw.strip()
        if not name:
            continue
        quantity = None
        parts = name.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            quantity, name = parts[0], parts[1]
        store.upsert_item(user_id, name, quantity, "manual")
    await update.message.reply_text("✍️ Added. " + fridge_text(user_id), parse_mode="Markdown")


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /remove eggs")
        return
    user_id = update.effective_user.id
    name = " ".join(context.args)
    if store.remove_item(user_id, name):
        await update.message.reply_text(f"🗑 Removed '{name}'.\n\n" + fridge_text(user_id), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Didn't find '{name}' in your fridge. /fridge to see what's there.")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store.clear_fridge(update.effective_user.id)
    await update.message.reply_text("🧹 Fridge cleared.")


async def prefer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        current = store.get_preference(update.effective_user.id) or "not set"
        await update.message.reply_text(
            f"Current preferences: {current}\n\nUsage: /prefer vegetarian, no shrimp, spicy food"
        )
        return
    prefs = " ".join(context.args)
    store.set_preference(update.effective_user.id, prefs)
    await update.message.reply_text(f"⚠️ Saved preferences: {prefs}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data["photos"] = []
    await update.message.reply_text("🧹 Photo buffer cleared. Send new photos.")


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data.setdefault("photos", [])
    if len(context.chat_data["photos"]) >= MAX_PHOTOS:
        await update.message.reply_text("Max photos for one analysis — /done when ready.")
        return
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    bytes_ = await file.download_as_bytearray()
    context.chat_data["photos"].append(bytes(bytes_))
    count = len(context.chat_data["photos"])
    logger.info("Collected photo %d/%d from chat %s", count, MAX_PHOTOS, update.effective_chat.id)
    await update.message.reply_text(f"📸 Got it ({count}/{MAX_PHOTOS}). More, or /done to analyze.")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photos: list[bytes] = context.chat_data.get("photos", [])
    if not photos:
        await update.message.reply_text("No photos in this session — send a fridge photo first.")
        return
    user_id = update.effective_user.id
    await update.message.reply_text("👀 Analyzing your fridge...")
    try:
        analysis = analyze_fridge_photos(photos)
    except Exception:
        logger.exception("Analysis failed")
        await update.message.reply_text("😕 Analysis failed. Try /reset and new photos.")
        return
    context.chat_data["photos"] = []
    for item in analysis.ingredients:
        store.upsert_item(user_id, item.name, item.quantity, item.confidence)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🍳 Find recipes", callback_data="find_recipes")]]
    )
    await update.message.reply_text(
        "✅ Merged into your fridge.\n\n" + fridge_text(user_id),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def find_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    items = store.get_fridge(user_id)
    if not items:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Fridge is empty — send photos or /add items first.")
        return
    await query.edit_message_reply_markup(reply_markup=None)
    msg = await query.message.reply_text("👨‍🍳 Thinking up recipes...")
    try:
        book = generate_recipes(
            [i.name for i in items],
            ["oil", "salt", "pepper", "flour", "sugar"],
            preferences=store.get_preference(user_id),
        )
    except Exception:
        logger.exception("Recipe generation failed")
        await msg.edit_text("😕 Couldn't generate recipes. Try again.")
        return
    context.chat_data["recipes"] = book.recipes
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{r.title} · {r.minutes}min", callback_data=f"recipe:{i}")]
            for i, r in enumerate(book.recipes)
        ]
    )
    await msg.edit_text("Pick a recipe 👇", reply_markup=keyboard)


async def show_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        recipe = context.chat_data["recipes"][int(query.data.split(":", 1)[1])]
    except (KeyError, IndexError, ValueError):
        await query.answer("Old buttons — start over with /start", show_alert=True)
        return
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(format_recipe(recipe), parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📸 Send 1-3 fridge photos, then /done — I detect and remember ingredients.\n\n"
        "/fridge — what I remember\n"
        "/add rice, soy sauce — add items manually (numbers become quantities: /add 3 eggs)\n"
        "/remove eggs — remove an item\n"
        "/clear — empty the fridge\n"
        "/prefer vegetarian, no shrimp — dietary preferences used in recipes\n"
        "/reset — clear unanalyzed photos"
    )


def main() -> None:
    store.init_db()
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("prefer", prefer_cmd))
    app.add_handler(CommandHandler("fridge", fridge_cmd))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, collect_photo))
    app.add_handler(CallbackQueryHandler(find_recipes, pattern="^find_recipes$"))
    app.add_handler(CallbackQueryHandler(show_recipe, pattern="^recipe:"))
    logger.info("Fridge Chef bot is running (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
