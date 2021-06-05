#!/usr/bin/python3

"""
Modular discord bot that supports dynamic reload of modularized commands.
"""

import json
import pathlib
import argparse

from discord.ext import commands
from discord import DiscordException, Embed, Game, Intents
from loguru import logger

from DynamicLoader import load_command, LOADED_LIST


def assign_basic_commands(bot: commands.bot):

    first_setup_done = False

    async def first_call():

        assign_expansion_commands()

        message = config["startup_message"]
        activity = config["bot_activity"]

        if message:
            await bot.get_channel(config["channel_id"]).send(message)

        if activity:
            await bot.change_presence(activity=Game(name=activity))

    # --------------------------------------

    @bot.event
    async def on_ready():
        nonlocal first_setup_done

        guild_id = config["guild_id"]

        logger.info(f"{bot.user} connected.")

        if not any(guild.id == guild_id for guild in bot.guilds):
            logger.critical("Bot is not connected to given server ID {}", guild_id)

            raise DiscordException(
                f"Bot is not connected to given server ID {guild_id}"
            )

        if not first_setup_done:
            first_setup_done = True

            await first_call()

    # --------------------------------------

    def assign_expansion_commands():

        for command_repr in load_command():
            command_repr.apply_command(bot)

    @bot.command(
        name="module",
        help="Shows/reload dynamically loaded commands. "
        "Use parameter 'reload' to reload edited/newly added modules.",
    )
    async def module(context: commands.Context, action="list"):

        logger.info("module [{}] called", action)

        if action == "reload":
            assign_expansion_commands()

        if action in ("reload", "list"):
            embed = Embed(title="Loaded Commands Status")

            for key, val in LOADED_LIST.items():
                mark = " ❌" if "Error" in val else ""
                embed.add_field(name=f"{key}{mark}", value=val, inline=False)

            await context.reply(embed=embed)
            return

        await context.reply(f"Got unrecognized action '{action}'!")

    # --------------------------------------


if __name__ == "__main__":

    # Parsing start

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-p",
        "--config-path",
        type=pathlib.Path,
        default=pathlib.Path(__file__).parent.joinpath("configuration.json"),
        help="Path to configuration file. Default is 'configuration.json' in current script's path.",
    )

    args = parser.parse_args()

    # end of parsing

    intent = Intents.default()
    intent.members = True

    config = json.loads(args.config_path.read_text())

    bot_ = commands.Bot(
        command_prefix="/",
        description=config["help_message"],
        help_command=commands.DefaultHelpCommand(no_category="Commands"),
        intents=intent
    )

    assign_basic_commands(bot_)

    try:
        bot_.run(config["discord_bot_token"])
    except DiscordException as err:
        logger.critical("DiscordException - is token valid? Details: {}", err)
