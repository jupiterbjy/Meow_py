"""
Module to forward message
"""

import pathlib
import json
import functools
from datetime import datetime
from io import BytesIO
from typing import Dict, Union, List

from telegram.ext import CallbackContext, Filters, MessageHandler, CommandHandler, BaseFilter
from telegram import Update, Document, Bot

from loguru import logger


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict[str, int] = json.loads(config_path.read_text())


def relay(update: Update, context: CallbackContext):
    where_ = update.effective_chat.id
    what_ = update.effective_message.message_id

    logger.debug("{}\n{}", where_, what_)

    try:
        target = config[str(update.effective_chat.id).removeprefix("-100")]
    except KeyError:
        print(config)
        return

    target = str(target) if str(target).startswith("-100") else "-100" + str(target)

    context.bot.forward_message(target, where_, what_)
    logger.debug("Forwarded message {} to {}, from {}", what_, target, where_)


__all__ = [
    MessageHandler(~(Filters.chat_type.private | Filters.command), callback=relay, run_async=True)
]
