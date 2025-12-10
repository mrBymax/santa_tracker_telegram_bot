import logging
import os

from settings import BOT_TOKEN

# Telegram library components
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram._utils.types import ReplyMarkup
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return

    user_name = update.effective_user.first_name
    # When pressed, sends Santa current location
    santa_location_btn = KeyboardButton("🎅🏻 Where is Santa now?")
    user_location_btn = KeyboardButton(
        "📍Notify Me when Santa is here", request_location=True
    )

    reply_markup = ReplyKeyboardMarkup(
        [[user_location_btn], [santa_location_btn]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if update.effective_chat:
        await context.bot.sendMessage(
            chat_id=update.effective_chat.id,
            text=f"🎅🏻 Ho Ho Ho, {user_name}!\n\nI can tell you where's Santa, and I can even notify you when's near you!\nYou can also set custom notifications for specific cities!\nTo get started press one of the buttons below!",
            reply_markup=reply_markup,
        )


def run_bot():
    """Entry point to start the bot."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing in settings.py or .env")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    # application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    # application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    print("🎅 Santa Bot is running...")
    application.run_polling()
