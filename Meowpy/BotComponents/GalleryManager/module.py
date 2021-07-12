"""
Auto assign module.
"""

import re
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
    WebhookMessage,
    Webhook,
    Attachment,
    AsyncWebhookAdapter
)
from loguru import logger

from .. import CogRepresentation


# --------------------------------------
# Global Variable setup and Config loading

# config loading

config_path = pathlib.Path(__file__).parent.joinpath("config.json")
configs = json.loads(config_path.read_text())

# convert config to int server key
configs = {int(channel_id): dict_ for channel_id, dict_ in configs.items()}

# Test directory. If this fails Error will be caught from main bot so that's fine.
DB_ROOT = pathlib.Path(__file__).parent.joinpath("database")
DB_ROOT.mkdir(exist_ok=True)

DB_PATH = (DB_ROOT.joinpath(str(key)) for key in configs.keys())

URL_PATTERN = re.compile(r"https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,4}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)")

# --------------------------------------


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

    # @staticmethod
    # async def webhook_send(url, content=None, embed=None, embeds=None, file=None) -> WebhookMessage:
    #     async with aiohttp.ClientSession() as session:
    #         webhook = Webhook.from_url(url, adapter=AsyncWebhookAdapter(session))
    #
    #         sent = await webhook.send(content, embed=embed, embeds=embeds, file=file, wait=True)
    #         return sent
    #
    # @staticmethod
    # async def webhook_delete(url, message_id):
    #     async with aiohttp.ClientSession() as session:
    #         webhook = Webhook.from_url(url, adapter=AsyncWebhookAdapter(session))
    #
    #         await webhook.delete_message(message_id)

    async def relay(self, message: Message, source: TextChannel) -> WebhookMessage:

        # webhook_url = self.configs[source.id]["webhook_url"]
        channel: TextChannel = source.guild.get_channel(self.configs[source.id]["post_channel"])

        try:
            attachment: Attachment = message.attachments[0]
        except IndexError:
            # this is link
            embed_original = message.embeds[0]

            # check if it's twitter, if so it's editable, give special work.
            if embed_original.footer.text and "Twitter" in embed_original.footer.text:
                # First clear unnecessary parts
                embed_original.clear_fields()
                embed_original.description = f"[Discord submission link]({message.jump_url})"
                return await channel.send(embed=embed_original)

            url = next(URL_PATTERN.finditer(message.content))[0]

            # check if we caught url
            content = url if url else message.content

            return await channel.send(content=f"Original post: {message.jump_url}\n\n{content}")
            # return await self.webhook_send(webhook_url, content=message.content, embed=embed)

        else:
            # something was uploaded, create new embed.

            embed = Embed(color=Color.from_rgb(107, 110, 119))
            embed.description = f"[Discord submission link]({message.jump_url})"
            embed.timestamp = message.created_at

            author: Member = message.author
            embed.set_author(name=author.display_name, icon_url=author.avatar_url)

            embed.set_footer(
                text="Discord",
                icon_url="https://discord.com/assets/f9bb9c4af2b9c32a2c5ee0014661546d.png",
            )

            # check type
            try:
                if "image" in attachment.content_type:
                    embed.set_image(url=attachment.url)
                    return await channel.send(embed=embed)
                else:
                    # consider as video for example
                    return await channel.send(embed=embed, file=await attachment.to_file())
            except TypeError:
                # no type specified, but message exists. consider it as image in that case

                # log attachment
                logger.warning("Attachment has no content_type. Detail: {}", attachment)

                embed.set_image(url=attachment.url)
                return await channel.send(embed=embed)

    def validate_reactor(self, payload: RawReactionActionEvent):

        try:
            config = self.configs[payload.channel_id]
        except (KeyError, TypeError):
            return False

        # logger.info("Got emoji_name {}, target: {}", emoji.name, config["marking_emoji"])

        if config["marking_emoji"] != payload.emoji.name:
            return False

        # check if post channel is within guild (to prevent attack)
        guild: Guild = self.bot.get_guild(payload.guild_id)
        if not guild.get_channel(config["post_channel"]):
            logger.critical("Channel {} does not exists in Guild {}!", config["post_channel"], guild.id)
            return False

        # check if reactor has permission to mark it.
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
        if payload.message_id in self.db[payload.channel_id]:
            return

        # relay to gallery channel
        channel_source: TextChannel = self.bot.get_channel(payload.channel_id)
        sent = await self.relay(await channel_source.fetch_message(payload.message_id), channel_source)

        # now prepare for db work
        self.db[payload.channel_id][payload.message_id] = sent.id

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):

        if not self.validate_reactor(payload):
            return

        if not self.configs[payload.channel_id]["delete_on_emoji_removal"]:
            return

        logger.info(
            f"Permitted user {payload.user_id} unmarked message {payload.message_id}."
        )

        db = self.db[payload.channel_id]

        if payload.message_id not in db:
            return

        # webhook_url = self.configs[payload.channel_id]["webhook_url"]
        # await self.webhook_delete(webhook_url, db[payload.message_id])
        channel: TextChannel = self.bot.get_channel(self.configs[payload.channel_id]["post_channel"])

        message: PartialMessage = channel.get_partial_message(db[payload.message_id])
        await message.delete()

        del db[payload.message_id]


__all__ = [CogRepresentation(ArtManagement)]
