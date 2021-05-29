import logging
import argparse
import asyncio

from discord.ext import commands
from discord import DiscordException, Embed
from discord.errors import HTTPException

from loguru import logger


end_signature = "\u200a\u200a\u200a"
end_signature_encoded = end_signature.encode("utf8")


def encode(string: str):
    string += end_signature

    return string.encode("utf8")


def decode(byte_string: bytes):
    decoded = byte_string.decode("utf8")

    return decoded.removeprefix(end_signature)


def assign_actions(bot):
    @bot.event
    async def on_ready():
        print(f"{bot.user} connected.")

        if not any(guild.id == args.guild_id for guild in bot.guilds):
            logger.critical("Bot is not connected to given server ID %s", args.guild_id)

            raise DiscordException(f"Bot is not connected to given server ID {args.guild_id}")

    # --------------------------------------

    linux_info_command = '''/etc/update-motd.d/00-header && /etc/update-motd.d/90-updates-available'''

    shell_field_commands = {
        "CPU / RAM": '''echo "CPU `LC_ALL=C top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}'`% RAM `free -m | awk '/Mem:/ { printf("%3.1f%%", $3/$2*100) }'`"''',
        "CPU Model": '''cat /proc/cpuinfo | awk -F : '/model name/ {print $2}' | head -1 | xargs''',
        "Disk usage": '''df -h | grep -e /dev/sd -e md'''
    }

    @bot.command(name="sysinfo")
    async def system_information(context: commands.Context):
        description_proc = await asyncio.create_subprocess_shell(linux_info_command, stdout=asyncio.subprocess.PIPE,
                                                                 stderr=asyncio.subprocess.PIPE)
        stdout, _ = await description_proc.communicate()

        description = stdout.decode(codec)

        embed = Embed(title="Brief System information", description=description)

        for key, val in shell_field_commands.items():
            proc = await asyncio.create_subprocess_shell(val, stdout=asyncio.subprocess.PIPE,
                                                         stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()

            embed.add_field(name=key, value=stdout.decode(codec), inline=True)

        await context.reply(embed=embed)

    # --------------------------------------

    @system_information.error
    async def system_info_error(context: commands.Context, error):
        await context.reply(f"```\n{error}\n```")

    # --------------------------------------

    @bot.command(name="run", help="Run cyan run!")
    async def run_literally(context: commands.Context):

        await context.send(
            "https://cdn.discordapp.com/attachments/783069235999014912/840531297499480084/ezgif.com-gif-maker.gif")

    # --------------------------------------

    codec = "utf8"
    code_format = "python3 <<EOF\n{}\nEOF"
    msg_format = "```\n{}\n```"
    overflow_msg = "..."

    @bot.command(name="py", help="Execute python code in Docker(not yet)")
    async def run_script(context: commands.Context, *, code: str):

        # check code safety in future
        # Extract code
        striped = code.strip()

        if striped.startswith("```python"):
            code = striped.removeprefix("```python").removesuffix("```")

        else:
            await context.reply("Please use ```python\n<code>\n``` format!")

        # Dumb way when it's not certain - put sequence of try-except, lel

        code_ = code_format.format(code)

        logger.info("Received code from %s by %s - detail: %s", context.channel, context.author, code_)

        try:
            proc = await asyncio.create_subprocess_shell(code_, stdout=asyncio.subprocess.PIPE,
                                                         stderr=asyncio.subprocess.PIPE)
        except Exception as err_:
            await context.reply(msg_format.format(err_))
            return

        try:
            stdout, stderr = await proc.communicate()
        except Exception as err_:
            await context.reply(f"{msg_format.format(err_)}\n\nExited with return code {proc.returncode}")
            return

        output = []

        if stdout:
            output.append(stdout.decode(codec))

        if stderr:
            output.append(stderr.decode(codec))

        message = "\n".join(output)

        exit_msg = f"\nExited with return code {proc.returncode}"

        try:
            await context.reply(msg_format.format(message) + exit_msg)
        except HTTPException as err_:

            if len(message) + len(exit_msg) + (len(msg_format) - 2) >= 2000:
                fitted = message[:2000 - len(overflow_msg) - len(exit_msg) - (len(msg_format) - 2)]
                cut_target = fitted.split("\n")[-1]
                message = fitted.removesuffix(cut_target) + overflow_msg

                await context.reply(message + exit_msg)
                return

            # This shouldn't run
            logger.debug("Got other http error: %s", err_)

    # --------------------------------------


if __name__ == '__main__':

    # Parsing start

    parser = argparse.ArgumentParser()

    parser.add_argument("bot_token", type=str, help="Bot's token")
    parser.add_argument("guild_id", type=int, help="Server's ID")

    args = parser.parse_args()

    bot_ = commands.Bot(command_prefix="/")
    assign_actions(bot_)

    try:
        bot_.run(args.bot_token)
    except DiscordException as err:
        logger.critical("DiscordException - is token valid? Details: %s", err)
