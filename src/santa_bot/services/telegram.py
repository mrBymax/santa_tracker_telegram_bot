import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from core.tracker import get_santa_status
from settings import BOT_TOKEN

# Telegram library components
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.ext._handlers.commandhandler import CommandHandler

# SantaBot components
from .santa_api import SantaAPI

"""
Project configuration
"""
api = SantaAPI()
route_data = api.get_route()


"""
Logger configuration
"""
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# When pressed, sends Santa current location
santa_location_btn = "🎅🏻 Where is Santa now?"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return

    user_name = update.effective_user.first_name
    user_location_btn = KeyboardButton(
        "📍Notify Me when Santa is here", request_location=True
    )
    status_btn = KeyboardButton(santa_location_btn)

    reply_markup = ReplyKeyboardMarkup(
        [[user_location_btn], [status_btn]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if update.effective_chat:
        await context.bot.sendMessage(
            chat_id=update.effective_chat.id,
            text=f"🎅🏻 Ho Ho Ho, {user_name}!\n\nI can tell you where's Santa, and I can even notify you when's near you!\nYou can also set custom notifications for specific cities!\nTo get started press one of the buttons below!",
            reply_markup=reply_markup,
        )


async def handle_santa_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    route = api.get_route()
    msg, current, next_stop = get_santa_status(route)

    photo_url = None

    # If Santa's at the city, use the city photo
    if current and "details" in current and current["details"]["photos"]:
        photo_url = current["details"]["photos"][0]["url"]

    # If it's flying return the destination photo
    elif next_stop and "details" in next_stop and next_stop["details"]["photos"]:
        photo_url = next_stop["details"]["photos"][0]["url"]

    if not update.effective_chat:
        return

    if photo_url:
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_url,
                caption=msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"Error sending photo {e}")
            # Fallback to default
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=msg, parse_mode="Markdown"
            )
    else:
        # No photo found, just send text
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=msg, parse_mode="Markdown"
        )


def run_bot():
    """Entry point to start the bot."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing in settings.py or .env")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.Text([santa_location_btn]), handle_santa_location)
    )

    print("Santa Bot is running...")
    application.run_polling()
