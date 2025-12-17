import asyncio
import logging
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, Optional, cast

# Geopy
from geopy.geocoders import Nominatim
from geopy.location import Location

# Telegram library components
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.ext._handlers.commandhandler import CommandHandler

from src.santa_bot.core.tracker import calculate_arrival_time, get_santa_status

# Settings
from src.santa_bot.settings import BOT_TOKEN

# SantaBot components
from .santa_api import SantaAPI

"""
Project configuration
"""
api = SantaAPI()
route_data = api.get_route()
geolocator = Nominatim(user_agent="whereissanta")
seen_users = set()

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
share_btn_text = "🎁 Share this bot with Friends"
custom_city_btn = "🌍 Notify Me when Santa is in [CITY]"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return

    user_name = update.effective_user.first_name
    user_id = update.effective_user.id

    if user_id not in seen_users:
        seen_users.add(user_id)
        logging.info(f"New user: {user_name} ({user_id})")

    status_btn = KeyboardButton(santa_location_btn)
    share_btn = KeyboardButton(share_btn_text)

    reply_markup = ReplyKeyboardMarkup(
        [[status_btn], [share_btn]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🎅🏻 Ho Ho Ho, {user_name}!\n\nI can tell you where's Santa, and I can even notify you when's near you!\nYou can also set custom notifications for specific cities!\nTo get started press one of the buttons below!",
            reply_markup=reply_markup,
        )


# Handle Santa's current location
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


# Set custom city notification
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

            if target_city not in notification_sub:
                notification_sub[target_city] = []
            if user_id not in notification_sub[target_city]:
                notification_sub[target_city].append(user_id)

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
                        f"🎅🏻 I've calculated Santa's flight path!\n"
                        f"He should be passing over **{target_city}** around **{time_str}**.\n\n"
                        f"✅ I've set a custom alarm for you at that exact time!"
                    ),
                    parse_mode="Markdown",
                )
                return
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎅🏻 Santa has already passed {target_city} this year!",
                )
                return
        # Fallback: nearest stop
    except Exception as e:
        print(f"Error: {e}")


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    user_id = update.effective_chat.id

    # List subscriptions for the user
    user_subs = [city for city, sub in notification_sub.items() if user_id in sub]

    if not user_subs:
        await context.bot.send_message(
            chat_id=user_id,
            text="🔕 You have no active subscriptions.\nUse `/notify <city>` to add one!",
            parse_mode="Markdown",
        )
        return

    user_subs.sort()

    msg = "🔔 Your active subscriptions:\n"
    msg += "\n".join(f"- {city}" for city in user_subs)

    await context.bot.send_message(
        chat_id=user_id,
        text=msg,
        parse_mode="Markdown",
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    user_id = update.effective_chat.id

    if context.args is None or len(context.args) == 0:
        await context.bot.send_message(
            chat_id=user_id,
            text="You need to specify a city to unsubscribe from.\nUsage: `/unsubscribe <city>`",
            parse_mode="Markdown",
        )
        return

    target_city = " ".join(context.args).title()

    if target_city in notification_sub and user_id in notification_sub[target_city]:
        notification_sub[target_city].remove(user_id)
        if not notification_sub[target_city]:
            del notification_sub[target_city]

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ You have unsubscribed from **{target_city}**.",
            parse_mode="Markdown",
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"You are not subscribed to **{target_city}**.",
            parse_mode="Markdown",
        )


# Return some statistics about this bot and Santa's journey
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    user_id = update.effective_chat.id

    # Global stats (user count, most popular city and total alerts)
    user_count = len(seen_users)
    total_alerts = len(notification_sub)
    total_active_alerts = sum(len(users) for users in notification_sub.values())

    # most popular city
    if notification_sub:
        top_count = max(len(users) for users in notification_sub.values())

        most_popular_cities = [
            city for city, users in notification_sub.items() if len(users) == top_count
        ]

        label = "Top Cities" if len(most_popular_cities) > 1 else "Top City"
        most_popular_city = f"🏆 **{label}:** {', '.join(sorted(most_popular_cities))} ({top_count} users)"
    else:
        most_popular_city = "🏆 **Top City:** None yet!"

    # User specific stats (cities subscribed, active alerts)
    user_city = [
        city for city, subscribers in notification_sub.items() if user_id in subscribers
    ]

    social_msg = ""
    if user_city:
        for city in user_city:
            others_count = len(notification_sub[city]) - 1
            if others_count > 0:
                social_msg += f"\n🎅🏻 Oh! Oh! Oh! Looks like **you and {others_count} others** are interested in Santa's path to **{city}**!"
            else:
                social_msg += f"\n🎅🏻 You are the **first one** waiting for Santa in **{city}**! Tell your friends!"
    else:
        social_msg = "\nYou aren't tracking any specific cities yet. Use `/notify <city>` to join!\n"

    report = (
        f"📊 **@where\\_is\\_santa\\_bot -- Real-Time Stats**\n"  # Note: '_' must be escaped in Markdown parse mode
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Trackers:** {user_count}\n"
        f"🌍 **Cities Watched:** {total_alerts}\n"
        f"🔔 **Active Alerts:** {total_active_alerts}\n"
        f"{most_popular_city}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{social_msg}"
    )

    await context.bot.send_message(chat_id=user_id, text=report, parse_mode="Markdown")
    return


async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    bot_username = context.bot.username

    share_text = (
        "Ho Ho Ho! 🎅🏻 I'm tracking Santa Claus in real-time! Check it out here:"
    )
    share_url = f"https://t.me/{bot_username}?start=ref_friend"

    safe_text = urllib.parse.quote(share_text)
    safe_url = urllib.parse.quote(share_url)

    telegram_share_link = f"https://t.me/share/url?url={safe_url}&text={safe_text}"
    inline_btn = InlineKeyboardButton("📤 Send to Contacts", url=telegram_share_link)
    reply_markup = InlineKeyboardMarkup([[inline_btn]])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Spread the holiday cheer! 🎄\nClick the button below to share the bot with your friends and family.",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show help information.
    Warning: This command should be manually updated each time a new command is added.
    """
    if not update.effective_chat:
        return

    help_text = (
        "🎄Oh Oh Oh! Here are the available commands:\n\n"
        "/start - Start the bot\n"
        "/list - List of the cities you're tracking\n"
        "/stats - Show statistics\n"
        "/notify - Set notification for a specific city\n"
        "/unsubscribe - Unsubscribe from a city\n"
        "/help - Show help (this menu)"
        "/share - Share the bot with your friends and family"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_text,
        parse_mode="HTML",
    )


async def post_init(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("list", "List subscriptions"),
        BotCommand("stats", "Show statistics"),
        BotCommand("notify", "Set notification"),
        BotCommand("unsubscribe", "Unsubscribe from a city"),
        BotCommand("help", "Show help"),
        BotCommand("share", "Share the bot with your friends and family"),
    ]

    await application.bot.set_my_commands(commands)


def run_bot():
    """Entry point to start the bot."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing in settings.py or .env")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.Text([santa_location_btn]), handle_santa_location)
    )
    application.add_handler(CommandHandler("notify", set_notification))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list", list_subscriptions))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(
        MessageHandler(filters.Regex(f"^{share_btn_text}$"), share_bot)
    )
    application.add_handler(CommandHandler("help", help_command))

    print("Santa Bot is running...")
    application.run_polling()
