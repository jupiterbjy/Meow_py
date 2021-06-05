import pathlib
import json
from datetime import datetime, timedelta
from typing import List

from discord.ext import tasks
from discord.ext.commands import Context, Cog, Bot
from discord import Embed, Member, Role, Guild, TextChannel
from loguru import logger

from . import CommandRepresentation, CogRepresentation


config_path = pathlib.Path(__file__).with_suffix(".json")
loaded_config = json.loads(config_path.read_text())


locals().update(loaded_config)
server_id: int
checking_channel_ids: List[int]
notify_at: int
from_role: int
new_role: int
check_last_days: int
minimum_joined_days: int
minimum_chats: int
check_interval_minute: int


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


def generate_congratulation_embed(member: Member, next_role: Role, day, count):

    embed = Embed(title=f"{member.display_name}", colour=next_role.colour)

    embed.set_thumbnail(url=str(member.avatar_url))
    embed.add_field(name="Member for", value=f"{day} days")
    embed.add_field(
        name=f"Chat for last {check_last_days} days", value=f"{count} times"
    )

    return embed


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
    if (day := (datetime.now() - member.joined_at).days) < minimum_joined_days:
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
            channel, member, check_last_days
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

    await context.reply(
        f"Congratulation <@{member.id}>, you're now a {next_role.name}!",
        embed=generate_congratulation_embed(member, next_role, day, idx + 1),
    )


class AssignCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        logger.info("Cog AssignTask starting.")
        self.task.start()

    def cog_unload(self):
        logger.info("Cog AssignTask stopping.")
        self.task.cancel()

    @tasks.loop(minutes=check_interval_minute)
    async def task(self):
        server: Guild = self.bot.get_guild(server_id)

        if not server:
            logger.critical("Given server ID {} does not exists! Is ID correct and bot exists in server?", server_id)
            return

        role_target: Role = server.get_role(from_role)

        for member in role_target.members:
            member: Member
            await self.check_member(member, server)

    @staticmethod
    async def check_member(member: Member, server: Guild):

        idx = -1

        target_role: Role = server.get_role(from_role)
        next_role: Role = server.get_role(new_role)
        roles: List[Role] = member.roles
        channels: List[TextChannel] = [ch for ch in server.channels if ch.id in checking_channel_ids]
        write_target: TextChannel = server.get_channel(notify_at)

        # check if user is already in higher role
        if next_role in roles:
            # This also less likely to happen. but just for fail safe.
            return

        # check if user is assigned to lower role
        if target_role not in roles:
            # This won't happen, but just for fail safe.
            return

        # check joined date
        if (day := (datetime.now() - member.joined_at).days) < minimum_joined_days:
            logger.debug(f"User <{member.display_name}> - insufficient join age ({day}/{minimum_joined_days})")
            return

        for channel in channels:
            channel: TextChannel

            logger.debug("Checking channel {}", channel.name)

            async for _ in member_chat_history_gen(channel, member, check_last_days):
                idx += 1

        if idx + 1 >= minimum_chats:
            await member.remove_roles(target_role)
            await member.add_roles(next_role)
        else:
            logger.debug(
                f"User <{member.display_name}> - insufficient chats in last {check_last_days}d "
                f"({idx + 1}/{minimum_chats})"
            )
            return

        # write a congratulation for member.

        await write_target.send(
            f"Congratulation <@{member.id}>! you're now a {next_role.name}!",
            embed=generate_congratulation_embed(member, next_role, day, idx + 1),
        )


__all__ = [
    CommandRepresentation(
        role_applicable,
        name="assignable",
        help="Show if user is applicable for assignation",
    ),
    CogRepresentation(AssignCog)
]
