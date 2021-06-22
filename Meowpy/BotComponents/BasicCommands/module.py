import asyncio
from datetime import datetime, timedelta
from typing import Union

from discord.ext.commands import Context
from discord.ext.commands.errors import EmojiNotFound
from discord import Embed, Member, Role, Asset, Emoji, errors
from loguru import logger

from BotComponents import CommandRepresentation


async def echo(context: Context, *args):

    logger.info("call on echo by {}\ncontent: {}", context.author, args)

    await context.reply(" ".join(args))


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

    for n in range(1, number + 1):
        await context.reply(f"Counting {n}/{number}!")
        await asyncio.sleep(abs((last := (last + delta)) - datetime.now()).total_seconds())


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


async def sticker_info(context: Context, *emojis: Emoji):
    # ref from https://stackoverflow.com/questions/54937474/

    for emoji in emojis:
        embed = Embed(description=f"\\<:{emoji.name}:{emoji.id}\\>", title=f"emoji: {emoji}")
        embed.add_field(name="id", value=emoji.id)
        embed.add_field(name="name", value=emoji.name)

        await context.reply(embed=embed)


async def sticker_info_error(context: Context, error):

    if isinstance(error, EmojiNotFound):
        await context.reply("I can't find such emoji in this server!")
        return

    logger.warning("Got error {}", error)


__all__ = [
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
