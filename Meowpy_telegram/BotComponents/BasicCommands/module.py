"""
Module for basic commands
"""
import pathlib
import json
from typing import Dict, List

import pytz
from dateutil import parser
from telegram.ext import CallbackContext, CommandHandler
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

    err_msg = f"Please provide with <local_timezone> <destination_timezone> <time_string> format!"

    args: List[str]
    try:
        local_tz, dest_tz, *time_str = args
    except ValueError:
        message.reply_text(err_msg)
        return

    time_str: str = " ".join(time_str)

    logger.debug(f"{local_tz}, {dest_tz}, {time_str}")

    # check if alias is in table, else use what provided
    if local_tz.lower() in tz_table:
        local_tz = tz_table[local_tz.lower()]

    if dest_tz.lower() in tz_table:
        dest_tz = tz_table[dest_tz.lower()]

    try:
        tz_src = pytz.timezone(local_tz)
        tz_dest = pytz.timezone(dest_tz)

        input_datetime = parser.parse(time_str)

    except (ValueError, pytz.exceptions.UnknownTimeZoneError) as err:
        logger.debug(err)
        message.reply_text(err_msg)
        return

    src_time = tz_src.localize(input_datetime)
    dest_time = src_time.astimezone(tz_dest)
    message.reply_text(f"{src_time.strftime(time_format)} {local_tz}\n{dest_time.strftime(time_format)} {dest_tz}")


__all__ = [
    CommandHandler("tzconv", convert_tz, run_async=True)
]
