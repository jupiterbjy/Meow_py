"""
Auto assign module.
"""

import pathlib
import json
import sqlite3
from typing import Dict

from discord.ext.commands import Cog, Bot
from discord import (
    Embed,
    Member,
    Message,
    TextChannel,
    Color,
    RawReactionActionEvent,
    PartialMessage,
    Guild,
)
from loguru import logger

from .. import CogRepresentation


# --------------------------------------
# Global Variable setup and Config loading

# config loading

config_path = pathlib.Path(__file__).parent.joinpath("config.json")
configs = json.loads(config_path.read_text())

# convert config to int server key
configs = {int(guild_id): dict_ for guild_id, dict_ in configs.items()}

# Test directory. If this fails Error will be caught from main bot so that's fine.
DB_ROOT = pathlib.Path(__file__).parent.joinpath("database")
DB_ROOT.mkdir(exist_ok=True)

DB_PATH = (DB_ROOT.joinpath(str(key)) for key in configs.keys())

# --------------------------------------


# async def fetch_channel_messages(
#     channel: TextChannel, emoji: str, whitelist_roles: Sequence[int]
# ) -> AsyncGenerator[Message, None]:
#     """
#     Generates Messages between given dates.
#     :param channel: TextChannel
#     :param emoji: unicode emoji used for marking
#     :param whitelist_roles: sequence of whitelisted roles.
#     """
#
#     roles = set(whitelist_roles)
#
#     message: Message
#     reaction: Union[Emoji, PartialEmoji, str]
#     author: Member
#     try:
#         async for message in channel.history(limit=None, oldest_first=False):
#
#             if emoji in message.reactions.emoji and roles & set(message.author.roles):
#                 yield message
#
#     except errors.Forbidden:
#         logger.warning(
#             "Cannot access to channel '{}' - ID: {}", channel.name, channel.id
#         )


class DBWrapper:
    def __init__(self, db_path: pathlib.Path):
        self.db_path = db_path

        if not self.db_path.exists():
            logger.info("Generating db at {}", self.db_path)
            con = sqlite3.connect(self.db_path)
            con.execute(
                "CREATE TABLE IF NOT EXISTS RELAYED(msg_id INTEGER PRIMARY KEY, copied_msg_id INTEGER)"
            )
            con.commit()
            con.close()

    def __setitem__(self, source_msg_id, relayed_msg_id):

        if source_msg_id in self:
            raise KeyError(f"Key {source_msg_id} already exists.")

        con = sqlite3.connect(self.db_path)

        con.execute(
            "INSERT INTO RELAYED(msg_id, copied_msg_id) VALUES(?, ?)",
            (source_msg_id, relayed_msg_id),
        )

        con.commit()
        con.close()

    def __delitem__(self, source_id):

        if source_id in self:
            con = sqlite3.connect(self.db_path)
            con.execute("DELETE from RELAYED WHERE msg_id = ?", (source_id,))

            con.commit()
            con.close()

    def __getitem__(self, source_id) -> int:

        if source_id in self:
            con = sqlite3.connect(self.db_path)
            cur = con.execute(
                "SELECT copied_msg_id from RELAYED WHERE msg_id = ?", (source_id,)
            )

            return cur.fetchone()[0]

    def __contains__(self, msg_id) -> bool:
        con = sqlite3.connect(self.db_path)
        cursor = con.execute(
            "SELECT EXISTS(SELECT 1 FROM RELAYED WHERE msg_id = ?)", (msg_id,)
        )

        output = cursor.fetchone()[0]
        con.close()

        return bool(output)


class ArtManagement(Cog):
    def __init__(self, bot: Bot):

        logger.info(f"[{type(self).__name__}] Init")

        self.bot = bot
        self.db: Dict[int, DBWrapper] = {
            int(db_path.stem): DBWrapper(db_path) for db_path in DB_PATH
        }
        self.configs = configs

    def cog_unload(self):
        logger.info(f"[{type(self).__name__}] Unloading")

    @staticmethod
    def generate_embed(source: Message) -> Embed:

        # if there's attachments, embed is ignored. Think it as priority.
        try:
            attachment = source.attachments[0]
        except IndexError:
            # this is link
            embed = source.embeds[0]
            embed.clear_fields()
        else:
            # if "image" in attachment.content_type:
            author: Member = source.author

            embed = Embed(color=Color.from_rgb(107, 110, 119))
            embed.set_author(name=author.display_name, icon_url=author.avatar_url)
            embed.set_footer(
                text="Discord",
                icon_url="https://discord.com/assets/f9bb9c4af2b9c32a2c5ee0014661546d.png",
            )
            embed.set_image(url=attachment.url)
            embed.timestamp = source.created_at

        embed.description = f"[Discord submission link]({source.jump_url})"

        return embed

    async def relay(self, message: Message, channel: TextChannel) -> Message:

        logger.info("On relay, channel: {}", channel.name)

        embed = self.generate_embed(message)
        sent = await channel.send(embed=embed)
        return sent

    def validate_reactor(self, payload: RawReactionActionEvent):

        try:
            config = self.configs[payload.guild_id]
        except (KeyError, TypeError):
            return False

        # check channel
        if config["channel_source"] != payload.channel_id:
            return False

        # logger.info("Got emoji_name {}, target: {}", emoji.name, config["marking_emoji"])

        if config["marking_emoji"] != payload.emoji.name:
            return False

        # check if reactor has permission to mark it.
        guild: Guild = self.bot.get_guild(payload.guild_id)
        user: Member = guild.get_member(payload.user_id)
        if not set(config["permitted_roles"]) & set(role.id for role in user.roles):
            return False

        return True

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):

        if not self.validate_reactor(payload):
            return

        logger.info(f"Permitted user {payload.user_id} marked message {payload.message_id}.")

        # check if message exists in db
        if payload.message_id in self.db[payload.guild_id]:
            return

        # relay to gallery channel
        channel_source: TextChannel = self.bot.get_channel(payload.channel_id)
        channel_target: TextChannel = self.bot.get_channel(self.configs[payload.guild_id]["channel_to_post"])
        sent = await self.relay(await channel_source.fetch_message(payload.message_id), channel_target)

        # now prepare for db work
        self.db[payload.guild_id][payload.message_id] = sent.id

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):

        if not self.validate_reactor(payload):
            return

        if not self.configs[payload.guild_id]["delete_on_emoji_removal"]:
            return

        logger.info(
            f"Permitted user {payload.user_id} unmarked message {payload.message_id}."
        )

        db = self.db[payload.guild_id]

        if payload.message_id not in db:
            return

        channel: TextChannel = self.bot.get_guild(payload.guild_id).get_channel(
            self.configs[payload.guild_id]["channel_to_post"]
        )
        message: PartialMessage = channel.get_partial_message(db[payload.message_id])

        await message.delete()

        del db[payload.message_id]


__all__ = [CogRepresentation(ArtManagement)]
