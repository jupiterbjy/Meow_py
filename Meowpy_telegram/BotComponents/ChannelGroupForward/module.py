"""
Module to forward message
"""

import pathlib
import json
from typing import Dict

from telegram.ext import CallbackContext, Filters, MessageHandler
from telegram import Update

from loguru import logger


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict[str, str] = json.loads(config_path.read_text())


def relay(update: Update, context: CallbackContext):
    where_ = update.effective_chat.id
    what_ = update.effective_message.message_id

    logger.debug("RECV {} FROM {}", what_, where_)

    try:
        target = config[str(where_).removeprefix("-100")]
    except KeyError:
        return

    target = target if target.startswith("-100") else "-100" + target

    context.bot.forward_message(target, where_, what_)
    logger.info("Forwarded message {} from {} to {}", what_, where_, int(target))


__all__ = [
    MessageHandler(~(Filters.chat_type.private | Filters.command), callback=relay, run_async=True)
]
