from datetime import datetime, timedelta, timezone
from typing import Iterable

from dateutil.parser import isoparse
from discord.ext.commands import Context
from discord import Embed, Colour, Member, Role, Asset, Guild, User, TextChannel
from loguru import logger

from . import CommandRepresentation


async def echo(context: Context, *args):

    logger.info("call on echo by {}\ncontent: {}", context.author, args)

    await context.reply(" ".join(args))


class TimeDeltaWrap:
    def __init__(self, time_delta: timedelta):
        self.delta = time_delta

    def __str__(self):
        if self.delta.days:
            return f"{self.delta.days}d"

        hour, seconds = divmod(self.delta.seconds, 3600)
        minute, seconds = divmod(seconds, 60)

        return f"{hour}h {minute}m {seconds}s"


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


async def joined(context: Context, user_id: int = 0):

    logger.info("call on joined with user_id: {}", user_id)

    if not user_id:
        member: Member = context.author
    else:
        member: Member = context.guild.get_member(user_id)

    try:
        role: Role = member.top_role
    except AttributeError:
        logger.warning("Could not find user. Is intent enabled?\nCached Member list: {}", context.guild.members)

        await context.reply(
            "Either member does not exist or Member Intent is disabled for me, I can't find that member."
        )
        return

    thumb: Asset = member.avatar_url

    embed = Embed(title=f"{member.display_name}", colour=role.color)

    now = datetime.now()
    discord_join = TimeDeltaWrap(now - member.created_at)
    member_join = TimeDeltaWrap(now - member.joined_at)

    premium = (
        TimeDeltaWrap(now - member.premium_since) if member.premium_since else None
    )

    embed.add_field(name="Discord joined", value=f"{discord_join}")

    embed.add_field(name="Server joined", value=f"{member_join}")

    if premium:
        embed.add_field(name="Boost since", value=f"{premium}")

    embed.set_footer(text=f"Primary role - {role.name}")
    embed.set_thumbnail(url=str(thumb))

    await context.reply(embed=embed)


__all__ = [
    CommandRepresentation(
        echo,
        name="echo",
        help="echo back your writings.",
    ),
    CommandRepresentation(
        joined,
        name="joined",
        help="Show your join dates. Pass Member ID to get that member's dates instead.",
    )
]
