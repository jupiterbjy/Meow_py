import pathlib
import json
from datetime import datetime, timedelta, timezone
from typing import List

from dateutil.parser import isoparse
from discord.ext.commands import Context
from discord import Embed, Colour, Member, Role, Asset, Guild, User, TextChannel
from loguru import logger

from . import CommandRepresentation


config_path = pathlib.Path(__file__).with_suffix(".json")
loaded_config = json.loads(config_path.read_text())


locals().update(loaded_config)
checking_channel_ids: List[int]
from_role: int
new_role: int
check_last_days: int
minimum_joined_days: int
minimum_chats: int


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

    logger.debug("Will fetch chats from {}", after_date)

    def filter_(message_):
        return message_.author == target_member

    async for message in channel.history(after=after_date).filter(filter_):
        yield message


async def role_applicable(context: Context):

    idx = -1

    member: Member = context.author
    target_role: Role = context.guild.get_role(from_role)
    next_role: Role = context.guild.get_role(new_role)
    roles: List[Role] = member.roles
    channels: List[TextChannel] = [ch for ch in context.guild.channels if ch.id in checking_channel_ids]

    # check if user is already in higher role
    if next_role in roles:
        await context.reply(f"User <@{member.id}> is already a member of {target_role.name}.")
        return

    # check if user is assigned to lower role
    if target_role not in roles:
        await context.reply(f"User <@{member.id}> is not a member of {target_role.name}.")
        return

    # check joined date
    if (day := (datetime.now() - context.author.joined_at).days) < minimum_joined_days:
        await context.reply(
            f"Any user need to stay at least {minimum_joined_days} days in "
            f"this server for assignment, however user <@{member.id}> stayed {day} days."
        )
        return

    start = datetime.now()
    for channel in channels:
        channel: TextChannel

        logger.debug("Checking channel {}", channel.name)

        async for _ in member_chat_history_gen(
            channel, context.author, check_last_days
        ):
            idx += 1

    end = datetime.now()

    logger.debug(f"Took {(end - start).seconds} sec.")

    if idx + 1 >= minimum_chats:
        await member.remove_roles(target_role)
        await member.add_roles(next_role)
    else:
        channel_msg = f"{', '.join(ch.name for ch in channels)}"

        await context.reply(
            f"User <@{member.id}> didn't make sufficient chats in last {check_last_days} days. "
            f"Make {minimum_chats - (idx + 1)} more in {channel_msg}!"
        )
        return

    embed = Embed(title=f"{member.display_name}", colour=next_role.colour)

    embed.set_thumbnail(url=str(member.avatar_url))
    embed.add_field(name="Member for", value=f"{day} days")
    embed.add_field(
        name=f"Chat for last {check_last_days} days", value=f"{idx + 1} times"
    )

    await context.reply(
        f"Congratulation <@{member.id}>, you're now a {next_role.name}!",
        embed=embed,
    )


__all__ = [
    CommandRepresentation(
        role_applicable,
        name="assignable",
        help="Show if user is applicable for assignation",
    ),
]
