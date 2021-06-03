#!/usr/bin/python3

import argparse
from discord.ext import commands
from discord import DiscordException, Embed, Game
from loguru import logger

from DynamicLoader import load_command, LOADED_MODULE


def assign_basic_commands(bot: commands.bot):

    first_setup_done = False

    async def first_call():

        message = "Meow World, Nyanstaree~🌟 I am a simple python bot you can play with. Type /help for usage!"

        await bot.change_presence(activity=Game(name="Cuddling Python"))
        await bot.get_channel(args.channel_id).send(message)

    @bot.event
    async def on_ready():
        nonlocal first_setup_done

        print(f"{bot.user} connected.")

        if not any(guild.id == args.guild_id for guild in bot.guilds):
            logger.critical("Bot is not connected to given server ID {}", args.guild_id)

            raise DiscordException(
                f"Bot is not connected to given server ID {args.guild_id}"
            )

        if not first_setup_done:
            first_setup_done = True

            await first_call()

    # --------------------------------------

    def assign_expansion_commands():

        for command_repr in load_command():
            command_repr.apply_command(bot)

    @bot.command(name="expansion", help="Shows/reload expansion commands.")
    async def expansion(context: commands.Context, action="list"):

        if action == "reload":
            assign_expansion_commands()

        if action in ("reload", "list"):
            embed = Embed(title="Dynamically loaded Commands")

            for key, val in LOADED_MODULE.items():
                embed.add_field(name=key, value=val, inline=False)

            await context.reply(embed=embed)
            return

        await context.reply(f"Got unknown action '{action}'!")

    # --------------------------------------


if __name__ == "__main__":

    # Parsing start

    parser = argparse.ArgumentParser()

    parser.add_argument("bot_token", type=str, help="Bot's token")
    parser.add_argument("guild_id", type=int, help="Server's ID")
    parser.add_argument("channel_id", type=int, help="Channel's ID")

    args = parser.parse_args()

    # end of parsing

    bot_ = commands.Bot(
        command_prefix="/",
        description="Meow World, Nyanstaree~🌟 I'm a playground bot, type /help for usage!",
        help_command=commands.DefaultHelpCommand(no_category="Commands"),
    )

    assign_basic_commands(bot_)

    try:
        bot_.run(args.bot_token)
    except DiscordException as err:
        logger.critical("DiscordException - is token valid? Details: {}", err)
