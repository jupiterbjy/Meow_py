import json
import pathlib
import logging
import argparse
import importlib
from typing import List, Union

from telegram.ext import Updater, Dispatcher, CommandHandler, Filters, MessageHandler
from loguru import logger


FOLDER_NAME = "BotComponents"
LOCATION = pathlib.Path(__file__).parent.joinpath(FOLDER_NAME)
LOADED_MODULES = []


def path_gen():
    for path_ in (p for p in LOCATION.iterdir() if p.is_dir()):
        cur = path_.joinpath("module.py")
        if cur.exists():
            yield cur


def load_command():
    for script in path_gen():
        try:
            module = importlib.import_module(
                ".".join((FOLDER_NAME, script.parent.stem, script.stem))
            )
            command_list: List[Union[CommandHandler, MessageHandler]] = getattr(module, "__all__")

        except Exception as err:
            logger.critical(
                "Got {} while importing expansion {}\n{}",
                type(err).__name__,
                script.parent.name,
                err,
            )

        else:
            yield from command_list


def start(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm an experimental bot, nothing is working properly!",
    )


def main(updater: Updater):
    dispatcher: Dispatcher = updater.dispatcher

    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    for handler in load_command():
        dispatcher.add_handler(handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Telegram port of meow.py")

    parser.add_argument(
        "-c",
        "--config",
        type=pathlib.Path,
        default=pathlib.Path("configuration.json"),
        help="Path to config file",
    )

    args = parser.parse_args()

    config_path: pathlib.Path = args.config

    loaded_config = json.loads(config_path.read_text())

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )

    main(Updater(token=loaded_config["telegram_bot_token"]))
