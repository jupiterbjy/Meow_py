"""
Module for basic commands
"""
import pathlib
import json
import pytz
from datetime import datetime
from typing import Dict, List

from telegram.ext import CallbackContext, Filters, CommandHandler
from telegram import Update

from loguru import logger


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict = json.loads(config_path.read_text())


def convert_tz(update: Update, context: CallbackContext):
    where_ = update.effective_chat.id
    args = context.args
    message = update.message
    user = message.from_user

    logger.debug("RECV {} FROM {} BY {}", args, where_, user)

    # name the config for my own good
    time_format = config["time_format"]
    tz_table = config["tz_table"]

    if not args or len(args) != 4:
        message.reply_text(f"Please provide with <local_timezone> <destination timezone> <{time_format}> format!")
        return

    args: List[str]
    local_tz, dest_tz, month_day, hour_minute = args

    # check if alias is in table, else use what provided
    if local_tz.lower() in tz_table:
        local_tz = tz_table[local_tz.lower()]

    if dest_tz.lower() in tz_table:
        dest_tz = tz_table[dest_tz.lower()]

    try:
        # I can't use dateutil parsers due to overlapping names

        tz_src = pytz.timezone(local_tz)
        tz_dest = pytz.timezone(dest_tz)

        month, day = map(int, month_day.split("-"))
        hour, minute = map(int, hour_minute.split(":"))

    except pytz.exceptions.UnknownTimeZoneError:
        message.reply_text(f"Please provide with <local_timezone> <destination timezone> <{time_format}> format!")
        return

    year = datetime.now().year
    src_time = datetime(year, month, day, hour, minute, tzinfo=tz_src)
    dest_time = src_time.astimezone(tz_dest)
    message.reply_text(f"{src_time.strftime('%m-%d %H:%M')} {local_tz}\n{dest_time.strftime('%m-%d %H:%M')} {dest_tz}")


__all__ = [
    CommandHandler("tzconv", convert_tz, run_async=True)
]
