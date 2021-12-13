"""
Module to Auto kick members joining the discussion group
"""

import pathlib
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict

from telegram.ext import CallbackContext, Filters, MessageHandler, CommandHandler
from telegram.error import BadRequest
from telegram import Update

from loguru import logger


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict[str, int] = json.loads(config_path.read_text())
whitelist = set()


def ban_on_join(update: Update, context: CallbackContext):
    where_ = update.effective_chat.id
    members = update.effective_message.new_chat_members

    if int(str(where_).removeprefix("-100")) not in config["group"]:
        return

    # logger.debug("{}{}", where_, members)

    length = timedelta(seconds=config["ban_seconds"])

    for member in members:

        if member.id in whitelist:
            whitelist.remove(member.id)
            continue

        try:
            context.bot.ban_chat_member(
                where_,
                member.id,
                revoke_messages=True,
                until_date=datetime.utcnow() + length,
            )
        except BadRequest:
            # check if bot was trying to ban itself
            if member.id != context.bot.id:
                # if not log it
                traceback.print_exc()

        logger.debug(
            "Banned user <{}> ID:{} for {} seconds, from {}",
            member.username,
            member.id,
            config["ban_seconds"],
            where_,
        )


def whitelist_user(update: Update, context: CallbackContext):

    user = update.effective_user.id

    logger.info("Called by {}", user)

    if user not in config["privilege"] or not context.args:
        update.message.reply_text("Missing parameter or Unauthorized call.")
        return

    try:
        id_ = int(context.args[0])
    except ValueError:
        update.message.reply_text("Wrong ID provided.")
        return

    whitelist.add(id_)
    logger.info("Added {} to whitelist.", id_)


__all__ = [
    MessageHandler(
        ~(Filters.chat_type.private | Filters.command),
        callback=ban_on_join,
        run_async=True,
    ),
    CommandHandler("auto_kick_whitelist", whitelist_user, run_async=True),
]
