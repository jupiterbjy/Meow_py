"""
Linux Command sets for showing system information where bot is running.
"""
import asyncio

from discord.ext.commands import Context
from discord import Embed
from loguru import logger

from .. import CommandRepresentation


linux_info_command = (
    """/etc/update-motd.d/00-header && /etc/update-motd.d/90-updates-available"""
)

shell_field_commands = {
    "CPU / RAM": '''echo CPU `lscpu | grep 'CPU MHz' | awk -F : '{gsub(/ /,""); print $2}'` MHz \| RAM `free -m | awk '/Mem:/ { printf("%3.1f%%", $3/$2*100) }'`''',
    "CPU Model": """cat /proc/cpuinfo | awk -F : '/model name/ {print $2}' | head -1 | xargs""",
    "Disk usage": """df -lh --total -x tmpfs | tail -1 | awk ' {print "Total", $2, "| Used", $3, "| Free", $4 }'""",
}


async def system_information(context: Context):
    logger.debug("Call on sysinfo.")

    description_proc = await asyncio.create_subprocess_shell(
        linux_info_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await description_proc.communicate()

    description = stdout.decode()

    logger.debug(description)

    embed = Embed(title="Brief System information", description=description)

    for key, val in shell_field_commands.items():
        proc = await asyncio.create_subprocess_shell(
            val, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()

        logger.debug(dec := stdout.decode())

        embed.add_field(name=key, value=dec, inline=False)

    await context.reply(embed=embed)


__all__ = [CommandRepresentation(system_information, name="sysinfo", help="Get general system info. But why?")]
