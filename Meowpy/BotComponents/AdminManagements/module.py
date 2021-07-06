"""
Module for some management needs.
"""
import asyncio
import pathlib
import json
from datetime import datetime, timedelta
from typing import List, Union, AsyncGenerator, Tuple

from discord.ext.commands import Context, Cog, Bot, command
from discord.ext.commands.errors import CommandInvokeError
from discord import (
    Embed,
    Color,
    Member,
    Guild,
    Message,
    errors,
    Asset,
    ActionRow,
    Button,
    ButtonColor,
    Interaction,
    ButtonClick,
    TextChannel,
)
from loguru import logger

from .. import CogRepresentation


config_path = pathlib.Path(__file__).parent.joinpath("config.json")
config = json.loads(config_path.read_text())

command_whitelist_roles: List[int]
log_channel: int

locals().update(config)


async def chat_history_gen(
    guild: Guild, from_date: Union[datetime, None], to_date: Union[datetime, None]
) -> AsyncGenerator[Message, None]:
    """
    Generates Messages between given dates.
    :param guild: Server(guild) ID
    :param from_date: Filter message since given date.
    :param to_date: Filter message before given date, including exact same date.
    """

    for channel in guild.text_channels:

        message: Message
        try:
            async for message in channel.history(
                after=from_date, before=to_date, limit=None, oldest_first=False
            ):

                if not message.author.bot:
                    yield message
        except errors.Forbidden:
            logger.warning(
                "Cannot access to channel '{}' - ID: {}", channel.name, channel.id
            )


def generate_target_embed(member: Member, reason: str):

    thumb: Asset = member.avatar_url

    embed = Embed(
        title=f"Purge for userid {member.id}",
        description="For reason: " + reason,
        color=Color.red(),
    )

    now = datetime.utcnow()
    discord_join = now - member.created_at
    member_join = now - member.joined_at

    embed.add_field(name="Name", value=member.display_name, inline=False)

    embed.add_field(
        name="Discord joined",
        value=f"{discord_join.days}d {discord_join.seconds // 3600}hr",
    )
    embed.add_field(
        name="Server joined",
        value=f"{int(member_join.total_seconds() / 60)}min",
        inline=True
    )

    embed.set_thumbnail(url=str(thumb))

    return embed


async def purge(
    guild: Guild, member: Member, reason: str, log_channel_id: Union[int, None] = None
):
    logger.info(f"Purging started for user id {member.id}")

    join_diff = datetime.utcnow() - member.joined_at

    logger.info(f"Banned user id {member.id}")

    await guild.ban(member, reason=reason, delete_message_days=7)

    if join_diff.days >= 7:

        # if not user was in server longer than that. prepare to remove.
        # prepare end time. a minor gap between utcnow at top and this one will be enough margin.
        until_ = datetime.utcnow() - timedelta(days=7)

        logger.info("User was in server longer than 7 days. Purging older messages.")

        counter = 0

        try:
            async for message in chat_history_gen(guild, member.joined_at, until_):
                if message.author == member:
                    counter += 1

                    await asyncio.sleep(0.1)

                    try:
                        await message.delete()
                    except CommandInvokeError:
                        while True:
                            await asyncio.sleep(0.5)
                            try:
                                await message.delete()
                            except CommandInvokeError:
                                pass
                            else:
                                break

        except errors.Forbidden as err:
            logger.critical(f"Bot has no permission to perform task.\nDetails: {err}")
            return

        logger.info(
            f"Deleted {counter} message(s) sent by [{member.display_name}/{member.id}]"
        )

    # If logging channel was not given, pass.
    if not log_channel_id:
        return

    # else get channel
    channel: TextChannel = guild.get_channel(log_channel_id)

    if not channel:
        logger.critical(f"No channel with id {log_channel_id} exists!")
        return

    # report to channel.
    embed = Embed(
        title=f"Purge report {datetime.utcnow()}",
        description=f"User is banned, all messages for last {join_diff.days} day(s) were removed.",
    )

    embed.timestamp = datetime.utcnow()
    embed.add_field(name="User ID", value=f"{member.id}", inline=False)
    embed.add_field(name="User Name", value=f"{member.display_name}", inline=False)
    embed.add_field(name="Reason", value=reason)

    await channel.send(embed=embed)


class PurgeCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        logger.info(f"[{type(self).__name__}] Init")

        self.pending_purges: List[Tuple[int, int, Member]] = []
        # Dict[target user id: purge issuer's id]

    def cog_unload(self):
        logger.info(f"[{type(self).__name__}] Unloading")

    @command(name="purge", descriptions="Show prompt to purge target user.")
    async def purge(
        self,
        context: Context,
        member_id: Union[Member, int] = 0,
        reason: str = "No reason specified.",
        *args: str
    ):

        logger.info("called, param: {} type: {}", member_id, type(member_id))

        reason += " " + " ".join(args)

        # Check issuer's role
        caller: Member = context.author

        if caller.top_role.id not in command_whitelist_roles:
            logger.warning(
                f"User id {caller.id} tried to invoke purge without permission."
            )
            return

        # Check target
        if isinstance(member_id, Member):
            target = member_id

        else:
            target = context.guild.get_member(member_id)

            if not target:
                await context.reply("Please provide the valid target!")
                return

        # target is valid, good to go.
        components = [
            ActionRow(
                Button(
                    label="Confirm",
                    emoji="✔️",
                    custom_id="perform_purge",
                    style=ButtonColor.red,
                ),
                Button(
                    label="Cancel",
                    emoji="❌",
                    custom_id="cancel_purge",
                    style=ButtonColor.grey,
                ),
            )
        ]

        embed = generate_target_embed(target, reason)
        message: Message = await context.reply(embed=embed, components=components)

        def inner_check(inter: Interaction, _: ButtonClick):
            return inter.message == message and inter.author.top_role.id in command_whitelist_roles

        bot: Bot = context.bot

        interaction, button = await bot.wait_for("button_click", check=inner_check)

        purge_confirm = button.custom_id == "perform_purge"

        await interaction.defer()

        if purge_confirm:
            await interaction.edit(
                embed=embed.set_footer(text="Purge started. This may take some time."),
                components=[components[0].disable_all_buttons()]
            )

            await purge(context.guild, target, reason, log_channel)

        await interaction.edit(
            embed=embed.set_footer(text="All done! Message will be removed in 10 seconds."),
            components=[components[0].disable_all_buttons()]
        )

        # cleanup command and message.
        await context.message.delete(delay=10)
        await message.delete(delay=10)


__all__ = [
    CogRepresentation(PurgeCog)
]
