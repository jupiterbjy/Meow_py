#!/usr/bin/python3

import argparse
import asyncio
import pathlib

from discord.ext import commands
from discord import DiscordException, Embed, File, Colour, Game
from loguru import logger
from traceback_with_variables import activate_by_import

from youtube_api_client import GoogleClient, VideoInfo


assert activate_by_import


end_signature = "\u200a\u200a\u200a"
end_signature_encoded = end_signature.encode("utf8")
record_path = (
    pathlib.Path(__file__)
    .parent.joinpath("YoutubeStreamStatLogger/Records/Cyan Nyan/")
    .absolute()
)


def encode(string: str):
    string += end_signature

    return string.encode("utf8")


def decode(byte_string: bytes):
    decoded = byte_string.decode("utf8")

    return decoded.removeprefix(end_signature)


def assign_actions(bot: commands.bot):

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

    linux_info_command = (
        """/etc/update-motd.d/00-header && /etc/update-motd.d/90-updates-available"""
    )

    shell_field_commands = {
        "CPU / RAM": '''echo "CPU `LC_ALL=C top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}'`% RAM `free -m | awk '/Mem:/ { printf("%3.1f%%", $3/$2*100) }'`"''',
        "CPU Model": """cat /proc/cpuinfo | awk -F : '/model name/ {print $2}' | head -1 | xargs""",
        "Disk usage": """df -h | grep -e /dev/sd -e md""",
    }

    @bot.command(name="sysinfo", help="Get general system info. But why?")
    async def system_information(context: commands.Context):

        logger.debug("Call on sysinfo.")

        description_proc = await asyncio.create_subprocess_shell(
            linux_info_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await description_proc.communicate()

        description = stdout.decode(codec)

        logger.debug(description)

        embed = Embed(title="Brief System information", description=description)

        for key, val in shell_field_commands.items():
            proc = await asyncio.create_subprocess_shell(
                val, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            logger.debug(dec := stdout.decode(codec))

            embed.add_field(name=key, value=dec, inline=False)

        await context.reply(embed=embed)

    # --------------------------------------

    @bot.command(name="run", help="Run cyan run!")
    async def run_literally(context: commands.Context):

        logger.debug("Call on run")

        await context.send(
            "https://cdn.discordapp.com/attachments/783069235999014912/840531297499480084/ezgif.com-gif-maker.gif"
        )

    # --------------------------------------

    codec = "utf8"

    @bot.command(name="py", help="Execute python code in Docker(not yet)")
    async def run_script(context: commands.Context, *, code: str):

        # Extract code
        striped = code.strip()

        if striped.startswith("```python"):
            code = striped.removeprefix("```python").removesuffix("```")

        else:
            await context.reply("Please use ```python\n<code>\n``` format!")

        # Dumb way when it's not certain - put sequence of try-except, lel

        # code_ = code_format.format(code)
        code_ = code

        logger.info(
            "Received code from {} by {}\ndetail: {}",
            context.channel,
            context.author,
            code_,
        )

        if not args.ip or not args.port:
            await context.reply(
                "Sorry! My owner didn't provide me either IP or Port, I can't access server for execution!"
            )
            return

        try:
            reader, writer = await asyncio.open_connection(args.ip, port=args.port)
        except Exception as err_:
            logger.critical(err_)
            logger.critical(f"IP was {args.ip}, and port was {args.port}")

            await context.reply(
                f"Encountered error on my side! It's not your fault!\n\n{err_}"
            )
            return

        # Send code
        send_byte = encode(code_)
        writer.write(send_byte)
        await writer.drain()
        logger.info("Sent {}", len(send_byte))

        # read data until delim is received
        data = b""

        try:
            while end_signature_encoded not in data:
                data += await asyncio.wait_for(reader.read(1024), timeout=10)
        except asyncio.TimeoutError:
            await context.reply("Got timeout error with your request! (< 10s)")
            return

        # decode and send it
        resp = decode(data)
        logger.debug("Got response, size {}", len(data))
        await context.reply(resp)

    # --------------------------------------

    @bot.command(
        name="streamgraph",
        help="Get stream's public statistics graph. Due to check interval and http errors, "
        "file may either be incomplete or not graphed at all.",
    )
    async def get_stream_image(context: commands.Context, index: int = 0):

        logger.debug("Call on stream, index {}.", index)

        files = [f for f in record_path.iterdir() if f.suffix == ".png"]

        sorted_files = sorted(files, reverse=True)

        try:
            target = sorted_files[index]
        except IndexError:
            index = len(sorted_files) - 1
            target = sorted_files[index]

        date, timestamp, video_id = target.stem.split("_", 2)
        link = f"https://youtu.be/{video_id}"

        with open(target, "rb") as fp:
            file = File(fp, f"{timestamp}.png")

        embed = Embed(
            title=f"Stream at {timestamp} epoch time",
            description=link,
            colour=Colour.from_rgb(24, 255, 255),
        )
        embed.set_image(url=f"attachment://{timestamp}.png")
        embed.set_thumbnail(url=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg")

        await context.reply(file=file, embed=embed)

    # --------------------------------------

    @get_stream_image.error
    async def get_stream_image_error(context: commands.Context, _):
        await context.reply("You passed wrong parameter! Value should be integer!")

    # --------------------------------------

    @bot.command(name="latest", help="Shows latest uploaded video.")
    async def get_latest(context: commands.Context):

        if not args.google_api:
            await context.reply("Sorry! My owner didn't provide me google API key, I can't use API!")
            return

        client = GoogleClient(args.google_api)

        new_ = client.get_latest_videos(args.channel_id, 1)[0]

        embed = Embed(
            title=new_.title,
            description=new_.description.strip.split("\n")[0],
            colour=Colour.from_rgb(24, 255, 255)
        )

        embed.set_image(url=new_.thumbnail_url())

        await context.reply(embed=embed)

    # --------------------------------------


if __name__ == "__main__":

    # Parsing start

    parser = argparse.ArgumentParser()

    parser.add_argument("bot_token", type=str, help="Bot's token")
    parser.add_argument("guild_id", type=int, help="Server's ID")
    parser.add_argument("channel_id", type=int, help="Channel's ID")
    parser.add_argument(
        "ip",
        type=str,
        default="",
        help="asyncio server's ip, if this is omitted you can't use python command.",
    )
    parser.add_argument(
        "port",
        type=int,
        default=0,
        help="asyncio server's port, if this is omitted you can't use python command.",
    )
    parser.add_argument("-g", "--google-api", type=str, default="", help="google data api key")

    args = parser.parse_args()

    bot_ = commands.Bot(
        command_prefix="/",
        description="Meow World, Nyanstaree~🌟 I'm a bot for cyan's robot playground!",
        help_command=commands.DefaultHelpCommand(no_category="Commands"),
    )
    assign_actions(bot_)

    try:
        bot_.run(args.bot_token)
    except DiscordException as err:
        logger.critical("DiscordException - is token valid? Details: {}", err)
