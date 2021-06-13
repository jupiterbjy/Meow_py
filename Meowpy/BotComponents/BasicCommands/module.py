import asyncio
from datetime import datetime, timedelta
from typing import Union

from discord.ext.commands import Context
from discord import Embed, Member, Role, Asset
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


def discord_stat_embed_gen(member: Member):
    try:
        role = member.top_role
    except AttributeError:
        role = None

    role: Union[Role, None]

    thumb: Asset = member.avatar_url

    embed = Embed(title=f"{member.display_name}", colour=role.color if role else None)

    now = datetime.utcnow()
    discord_join = TimeDeltaWrap(now - member.created_at)
    member_join = TimeDeltaWrap(now - member.joined_at)

    premium = (
        TimeDeltaWrap(now - member.premium_since) if member.premium_since else None
    )

    embed.add_field(name="Discord joined", value=f"{discord_join}")

    embed.add_field(name="Server joined", value=f"{member_join}")

    if premium:
        embed.add_field(name="Boost for", value=f"{premium}")

    if role:
        embed.set_footer(text=f"Primary role - {role.name}")

    embed.set_thumbnail(url=str(thumb))

    return embed


async def joined(context: Context, user_id: int = 0):

    logger.info("call on joined with user_id: {}", user_id)

    if not user_id:
        member: Member = context.author
    else:
        member: Member = context.guild.get_member(user_id)

    await context.reply(embed=discord_stat_embed_gen(member))


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
    )
]
