import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from core.tracker import calculate_arrival_time, get_santa_status

# Geopy
from geopy.geocoders import Nominatim
from geopy.location import Location

# Settings
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
geolocator = Nominatim(user_agent="whereissanta")

"""
Logger configuration
"""
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Map to keep track of the cities used by users
# Since the user base is pretty small, a hashmap is enough

notification_sub = {}  # Format: { "city" : [user_id] }

# When pressed, sends Santa current location
santa_location_btn = "🎅🏻 Where is Santa now?"
custom_city_btn = "🌍 Notify Me when Santa is in [CITY]"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return

    user_name = update.effective_user.first_name
    # user_location_btn = KeyboardButton(
    #     "📍Notify Me when Santa is here", request_location=True
    # )
    status_btn = KeyboardButton(santa_location_btn)
    # custom_city = KeyboardButton(custom_city_btn)

    reply_markup = ReplyKeyboardMarkup(
        [[status_btn]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if update.effective_chat:
        await context.bot.send_message(
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


# Alert for cities not present in data
async def send_custom_alert(context: ContextTypes.DEFAULT_TYPE):
    job = context.job

    if not job or not job.data:
        return

    job_data = cast(Dict[str, Any], job.data)  # needs to be explicitly casted!

    user_id = job_data["user_id"]
    city_name = job_data["city"]

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🚨 **SANTA ALERT!** 🚨\n\nSanta is estimated to be flying near **{city_name}** right now! 👀 Look up!",
        parse_mode="Markdown",
    )


async def set_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    user_id = update.effective_chat.id

    # Check if the user asked for a city
    if context.args is None or len(context.args) == 0:
        await context.bot.send_message(
            chat_id=user_id,
            text="Ho Ho Ho! You forgot to tell me the city!\nUsage: `/notify <city_name>`",
            parse_mode="Markdown",
        )
        return

    target_city = " ".join(context.args).title()
    route = api.get_route()
    valid_cities = {stop["city"]: stop for stop in route}

    # Exact Match
    if target_city in valid_cities:
        if target_city not in notification_sub:
            notification_sub[target_city] = []

        if user_id not in notification_sub[target_city]:
            notification_sub[target_city].append(user_id)

            stop_data = valid_cities[target_city]

            arrival_ts = stop_data["arrival"] / 1000
            dt_object = datetime.fromtimestamp(arrival_ts)
            time_str = dt_object.strftime("%d %B at %H:%M")

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ All set! I'll send you a message when Santa arrives in {target_city}!\n"
                + f"He should be passing over **{target_city}** around **{time_str}**.\n\n",
                parse_mode="Markdown",
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"‼️ You are already watching {target_city}!",
            )
        return

    # Geocode Fallback
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔍 '{target_city}' isn't on the main route. Checking for the closest stop...",
    )

    try:
        loop = asyncio.get_running_loop()

        raw_result = await loop.run_in_executor(
            None, lambda: geolocator.geocode(target_city)
        )

        location = cast(Optional[Location], raw_result)

        if location is None:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"I could not find {target_city}. Are you sure of the spelling?",
            )
            return

        lat = location.latitude
        lon = location.longitude

        eta_ms = calculate_arrival_time(lat, lon, route)
        if eta_ms:
            # convert to seconds (for JobQueue)
            eta_s = eta_ms / 1000
            current_time_s = time.time()
            delay = eta_s - current_time_s

            if delay > 0 and context.job_queue:
                # Schedule the alert
                context.job_queue.run_once(
                    send_custom_alert,
                    when=delay,
                    data={"user_id": user_id, "city": target_city},
                )

                # Pretty print the time
                dt_object = datetime.fromtimestamp(eta_s)
                time_str = dt_object.strftime("%d %B at %H:%M:%S")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎅 I've calculated Santa's flight path!\n"
                        f"He should be passing over **{target_city}** around **{time_str}**.\n\n"
                        f"✅ I've set a custom alarm for you at that exact time!"
                    ),
                    parse_mode="Markdown",
                )
                return
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎅 Santa has already passed {target_city} this year!",
                )
                return
        # Fallback: nearest stop
    except Exception as e:
        print(f"Error: {e}")


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
    application.add_handler(CommandHandler("notify", set_notification))

    print("Santa Bot is running...")
    application.run_polling()
