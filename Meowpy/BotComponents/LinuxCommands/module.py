"""
Linux Command sets for showing system information where bot is running.
"""
import asyncio
import json
import pathlib

from discord.ext.commands import Context
from discord import Embed
from loguru import logger

from .. import CommandRepresentation


config_path = pathlib.Path(__file__).parent.joinpath("config.json")
loaded_config = json.loads(config_path.read_text())


async def system_information(context: Context):
    logger.debug("Called")

    guild_id = str(context.guild.id)
    author_id = context.author.id

    if guild_id not in loaded_config or author_id not in loaded_config[guild_id]["command_whitelist"]:
        logger.warning("Unauthorized call by [{}]", author_id)

        await context.reply("You're not in whitelist!")
        return

    description_proc = await asyncio.create_subprocess_shell(
        loaded_config[guild_id]["linux_info_command"],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await description_proc.communicate()

    description = stdout.decode()

    logger.debug(description)

    embed = Embed(title="Brief System information", description=description)

    for key, val in loaded_config[guild_id]["commands"].items():
        proc = await asyncio.create_subprocess_shell(
            val, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()

        logger.debug(dec := stdout.decode())

        embed.add_field(name=key, value=dec, inline=False)

    await context.reply(embed=embed)


__all__ = [CommandRepresentation(system_information, name="sysinfo", help="Get general system info. But why?")]
