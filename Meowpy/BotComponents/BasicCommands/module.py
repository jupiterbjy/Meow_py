import json
import pathlib
import asyncio
import unicodedata
from datetime import datetime, timedelta
from typing import Union, Dict, List

import pytz
from dateutil import parser
from discord.ext.commands import Context
from discord.ext.commands.errors import EmojiNotFound
from discord import Embed, Member, Role, Asset, Emoji, errors, Message
from loguru import logger

from BotComponents import CommandRepresentation


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict = json.loads(config_path.read_text())


async def time(context: Context):

    logger.info("call by {}", context.author)

    format_ = "%mM %dD %H:%M:%S"
    now_dt = datetime.now()
    utc_now_dt = now_dt.utcfromtimestamp(now_dt.timestamp())

    now = now_dt.strftime(format_)
    utc_now = utc_now_dt.strftime(format_)
    msg_utc = context.message.created_at.strftime(format_)

    diff = f"{(now_dt.utcnow() - context.message.created_at).total_seconds():.2f} sec"

    embed = Embed(title="Server time")
    embed.add_field(name="\u200b", value="\n".join(("Server", "Server(UTC)", "Message(UTC)", "Diff")))
    embed.add_field(name="\u200b", value="\n".join((now, utc_now, msg_utc, diff)))

    await context.reply(embed=embed)


async def ping(context: Context):
    recv_ts = datetime.utcnow()
    create_ts = context.message.created_at

    diff = (recv_ts - create_ts).total_seconds() * 1000

    logger.info("ping by {}, {}ms", context.author, diff)

    await context.reply(f"Pong! {diff:.2f}ms!")


async def echo(context: Context, *args):

    logger.info("call by {}\ncontent: {}", context.author, args)

    await context.reply(" ".join(args))


async def convert_tz(context: Context, *args):
    message: Message = context.message
    logger.debug("call by {}, args: {}", context.author, args)

    # name the config for my own good
    time_format = config["time_format"]
    tz_table = config["tz_table"]

    err_msg = f"Please provide with <local_timezone> <destination_timezone> <time_string> format!"


    args: List[str]
    try:
        local_tz, dest_tz, *time_str = args
    except ValueError:
        await message.reply(err_msg)
        return

    time_str: str = " ".join(time_str)

    # check if alias is in table, else use what provided
    if local_tz.lower() in tz_table:
        local_tz = tz_table[local_tz.lower()]

    if dest_tz.lower() in tz_table:
        dest_tz = tz_table[dest_tz.lower()]

    try:
        tz_src = pytz.timezone(local_tz)
        tz_dest = pytz.timezone(dest_tz)

        input_datetime = parser.parse(time_str)

    except (ValueError, pytz.exceptions.UnknownTimeZoneError):
        await message.reply_text(err_msg)
        return

    src_time = tz_src.localize(input_datetime)
    dest_time = src_time.astimezone(tz_dest)
    await message.reply(f"{src_time.strftime(time_format)} {local_tz}\n"
                        f"{dest_time.strftime(time_format)} {dest_tz}\n"
                        f"(Will be updated to use combo box later)")


async def countdown(context: Context, number: int = 5):

    logger.info("call on countdown by {}\ncount: {}", context.author, number)

    if number < 1:
        await context.reply("Nothing to count!")
        return

    if number > 10:
        await context.reply("Can't count more than 10, or I'll be rendered a spam!")
        return

    delta = timedelta(seconds=1)
    last = datetime.now()

    message = await context.reply(f"Counting 1/{number}!")

    for n in range(2, number + 1):
        await asyncio.sleep(abs((last := (last + delta)) - datetime.now()).total_seconds())

        await message.edit(content=f"Counting {n}/{number}!")


async def member_chat_history_gen(channel, target_member: Member, max_date=3):

    max_duration = timedelta(days=max_date)

    # check join date to not fetch older messages
    if (datetime.now() - target_member.joined_at) < max_duration:
        after_date = target_member.joined_at
    else:
        after_date = datetime.now() - max_duration

    def filter_(message_):
        return message_.author == target_member

    async for message in channel.history(after=after_date).filter(filter_):
        yield message


def discord_stat_embed_gen(member: Member):
    try:
        role = member.top_role
    except AttributeError:
        role = None

    role: Union[Role, None]

    thumb: Asset = member.avatar_url

    embed = Embed(title=f"{member.display_name}", colour=role.color if role else None)

    now = datetime.utcnow()
    discord_join = now - member.created_at
    member_join = now - member.joined_at

    premium = (
        (now - member.premium_since) if member.premium_since else None
    )

    embed.add_field(name="Discord joined", value=f"{discord_join.days}d {discord_join.seconds // 3600}hr")
    embed.add_field(name="Server joined", value=f"{member_join.days}d {member_join.seconds // 3600}hr")

    if premium:
        embed.add_field(name="Boost for", value=f"{premium.days}d {premium.seconds // 3600}hr")

    if role:
        embed.set_footer(text=f"Primary role - {role.name}")

    embed.set_thumbnail(url=str(thumb))

    return embed


async def joined(context: Context, member_id: Union[Member, int] = 0):

    logger.info("called, param: {} type: {}", member_id, type(member_id))

    if not member_id:
        member: Member = context.author

    elif isinstance(member_id, Member):
        member = member_id
    else:
        member: Member = context.guild.get_member(member_id)

    if not member:
        await context.reply("No such member exists!")
        return

    try:
        await context.reply(embed=discord_stat_embed_gen(member))
    except errors.Forbidden:
        logger.warning("No permission to write to channel [{}] [ID {}].", context.channel.name, context.channel.id)


async def sticker_info(context: Context, *emojis: Union[Emoji, str]):
    # ref from https://stackoverflow.com/questions/54937474/

    logger.info("called, param: {}", emojis)

    for emoji in emojis:
        try:
            embed = Embed(description=f"\\<:{emoji.name}:{emoji.id}\\>", title=f"emoji: {emoji}")
            embed.add_field(name="id", value=emoji.id)
            embed.add_field(name="name", value=emoji.name)

        except AttributeError:
            # Then unicode emoji

            name = unicodedata.name(emoji).replace(" ", "_")
            code = json.dumps(emoji)[1:-1]
            # code = emoji.encode("unicode-escape").decode("utf8")

            embed = Embed(description=code, title=f"Unicode emoji: {emoji}")
            embed.add_field(name="id", value="None (Unicode)")
            embed.add_field(name="utf standard name", value=name)

        await context.reply(embed=embed)


async def sticker_info_error(context: Context, error):

    logger.warning("Got error {}", error)

    if isinstance(error, EmojiNotFound):
        await context.reply("I can't find such emoji in this server!")
        return


__all__ = [
    CommandRepresentation(
        time,
        name="time",
        help="Display server time",
    ),
    CommandRepresentation(
        ping,
        name="ping",
        help="",
    ),
    CommandRepresentation(
        convert_tz,
        name="tzconv",
        help="<local_timezone> <destination_timezone> <time_str}>",
    ),
    CommandRepresentation(
        echo,
        name="echo",
        help="Echo back your writings.",
    ),
    CommandRepresentation(
        countdown,
        name="countdown",
        help="Starts countdown, can't set longer than 10.",
    ),
    CommandRepresentation(
        joined,
        name="joined",
        help="Show your join dates. Pass Member ID to get that member's dates instead.",
    ),
    CommandRepresentation(
        sticker_info,
        err_handler=sticker_info_error,
        name="stickerinfo",
        help="Shows debugging data of the sticker."
    )
]
