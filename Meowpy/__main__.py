#!/usr/bin/python3.9

"""
Modular discord bot that supports dynamic reload of modularized commands.
"""

import json
import pathlib
import argparse

from discord.ext import commands
from discord import DiscordException, Embed, Game, Intents, Member
from loguru import logger

from DynamicLoader import load_command, LOADED_LIST, LOADED_FILE_HASH


def assign_basic_commands(bot: commands.bot):

    first_setup_done = False

    logger.info("Adding event first_call")

    async def first_call():

        assign_expansion_commands()

        activity = config["bot_activity"]

        if activity:
            await bot.change_presence(activity=Game(name=activity))

    # --------------------------------------
    logger.info("Adding event on_ready")

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

    add_failed = {}

    def assign_expansion_commands():

        add_failed.clear()

        loaded = load_command(bot)

        for representation in loaded:
            try:
                representation.add(bot)
            except Exception as err_:
                add_failed[representation.name] = f"{type(err_).__name__}"
                logger.critical(err_)

        return set(map(lambda x: x.name, loaded)), set(add_failed.keys())

    logger.info("Adding command reload")

    @bot.command(
        name="module",
        help="Shows/reload dynamically loaded commands. "
        "Use parameter 'reload' to reload edited/newly added modules.",
    )
    async def module(context: commands.Context, action: str = "list", target: str = ""):

        logger.info("called, param: {}, {}", action, target)
        member: Member = context.author

        if action == "reload":

            if member.id in config["reload_whitelist"]:
                logger.info("Authorised reload call from '{}'", member.display_name)

                embed = Embed(title="Reload report")

                if target:
                    # find a matching key
                    key = [k for k in LOADED_FILE_HASH.keys() if k.stem == target]
                    try:
                        LOADED_FILE_HASH.pop(key[0])
                    except (KeyError, IndexError):
                        embed.description = f"Reload fail: {target} is not found."
                new, failed = assign_expansion_commands()

                embed.add_field(name="Newly Loaded", value="\n".join(new - failed) + "\u200b")
                embed.add_field(name="Failed to load", value="\n".join(failed) + "\u200b")

                for key, val in LOADED_LIST.items():
                    if "Error" in val:
                        embed.add_field(name=f"{key} ❌", value=val, inline=False)

                await context.reply(embed=embed)
                return

            else:
                logger.warning("Unauthorised reload call from '{}'", member.display_name)

        if action == "list":
            embed = Embed(
                title="Loaded Commands/Cogs Status",
                description="Commands shown on failed list is disabled.",
            )

            for key, val in LOADED_LIST.items():
                mark = " ❌" if "Error" in val else ""

                embed.add_field(name=f"{key}{mark}", value=val, inline=False)

            if add_failed:
                text = "\n".join(f"{key} - {val}" for key, val in add_failed.items())
                embed.add_field(name="Commands Disabled", value=text)

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
        help="Path to configuration fil e. Default is 'configuration.json' in current script's path.",
    )

    args = parser.parse_args()

    # end of parsing

    intent = Intents.default()
    intent.members = True
    intent.messages = True
    intent.reactions = True
    intent.webhooks = True

    config = json.loads(args.config_path.read_text())

    logger.info("Configuration loaded.")

    bot_ = commands.Bot(
        command_prefix=config["prefix"],
        description=config["help_message"],
        help_command=commands.DefaultHelpCommand(no_category="Commands"),
        intents=intent,
    )

    logger.info("Assigning submodules")

    # log config
    # log_p = pathlib.Path(__file__).parent.joinpath("log/{time}.log")
    # logger.add(log_p, rotation="5MB", retention="7 days", compression="zip")

    assign_basic_commands(bot_)

    logger.info("Starting bot")

    try:
        bot_.run(config["discord_bot_token"])
    except DiscordException as err:
        logger.critical("DiscordException - is token valid? Details: {}", err)
