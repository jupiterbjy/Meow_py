import asyncio
import pathlib
import json
from datetime import datetime
from typing import Dict, Union, List

from pytchat import LiveChatAsync
from pytchat.processors.default.processor import Chatdata, Chat
from discord.ext.commands import Cog, Bot, Context, command
from discord.ext import tasks
from discord.embeds import EmptyEmbed
from discord import Embed, TextChannel, Colour
from loguru import logger


from .. import CogRepresentation


config_path = pathlib.Path(__file__).parent.joinpath("config.json")
config: Dict[str, Union[str, int]] = json.loads(config_path.read_text())

yt_vid_id: str
discord_ch_id: int
interval_sec: int
timezone_str: str
command_whitelist: List[int]
role_symbol: Dict[str, str]
emoji_mapping: Dict[str, str]

locals().update(config)


def argb_to_rgb(argb: int):
    # what a mess..
    if not argb:
        return 0

    # converting int to hex string, strip 0x, zfill to 8 width argb, strip alpha.
    return int(hex(argb)[2:].zfill(8)[2:], base=16)


def error_to_embed(err: Exception):
    return Embed(title=str(type(err).__name__), description=err)


class YoutubeChatRelayCog(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.vid_id = yt_vid_id

        logger.info("[ChatRelay] starting.")

        self.livechat: Union[LiveChatAsync, None] = None

        self.load_livechat()

    def cog_unload(self):
        logger.info("[ChatRelay] Stopping.")

        self.livechat.terminate()

    @staticmethod
    def embed_apply_type(embed: Embed, json_data: dict):
        """
        Adds corresponding stuffs to embed based on message's type.

        :param embed: Discord embed
        :param json_data: mapping type from message json.
        """

        type_: str = json_data["type"]

        # originally thought of using dict and lambda, but this was much simpler.
        # obviously ordered to most frequent order.

        if type_ == "textMessage":
            pass

        elif type_ == "superChat":
            embed.title = json_data["amountString"]

        elif type_ == "newSponsor":
            embed.title = "New member"
            embed.colour = Colour(value=int("0f9d5", base=16))

        elif type_ == "superSticker":
            embed.title = json_data["amountString"]
            embed.set_thumbnail(url=json_data["sticker"])

    @staticmethod
    def embed_set_author(embed: Embed, json_data: dict):
        """
        Adds author fields to embed.

        :param embed: Discord embed
        :param json_data: mapping type from message json.
        """

        author_dict: dict = json_data["author"]

        # prep icon
        icon = url if (url := author_dict["imageUrl"]) else EmptyEmbed

        # determine role
        if author_dict["isChatOwner"]:
            role = "owner"
        elif author_dict["isChatModerator"]:
            role = "moderator"
        elif author_dict["isChatSponsor"]:
            role = "member"
        else:
            role = "default"

        name = " ".join((author_dict["name"], role_symbol[role]))

        embed.set_author(name=name, url=author_dict["channelUrl"], icon_url=icon)

    async def callback(self, chat_data: Chatdata):
        """
        Callback running in LiveAsyncChat

        :param chat_data:
        :return:
        """

        channel: TextChannel = self.bot.get_channel(discord_ch_id)

        async for chat in chat_data.async_items():
            chat: Chat

            json_data: dict = json.loads(chat.json())

            logger.debug(f"Received json:\n{json.dumps(json_data, indent=2)}\n")

            # prepare message
            message: str = json_data["message"]

            for yt_emoji, dc_image in emoji_mapping.items():
                if yt_emoji in message:
                    message = message.replace(yt_emoji, dc_image)

            bg_color: int = argb_to_rgb(json_data["bgColor"])

            # Start writing embed
            embed = Embed(description=message, colour=bg_color)

            # write author and type specific stuffs
            self.embed_apply_type(embed, json_data)
            self.embed_set_author(embed, json_data)

            # set utc time
            timestamp = json_data["timestamp"] / 1000.0

            embed.timestamp = datetime.utcfromtimestamp(timestamp)
            # embed.set_footer(text=f"{utc_aware.strftime(type_ + ' %Y-%m-%d %H:%M:%S (UTC)')}")

            try:
                await channel.send(embed=embed)

            except AttributeError:
                logger.critical("Unknown channel ID {}, check configuration!", discord_ch_id)

    def load_livechat(self):
        try:
            # if self.livechat.is_alive():
            self.livechat.terminate()
        except (AttributeError, RuntimeError):
            pass

        stream = LiveChatAsync(self.vid_id, callback=self.callback)
        stream.raise_for_status()

        self.livechat = stream

    @tasks.loop(count=1)
    async def relay_task(self):
        channel: TextChannel = self.bot.get_channel(discord_ch_id)

        while True:
            await channel.send("Chat relay started!")

            while self.livechat.is_alive():
                await asyncio.sleep(5)

            try:
                self.livechat.raise_for_status()

            except Exception as err:
                logger.warning("Got {}.\nDetail: {}", type(err).__name__, err)

                embed = error_to_embed(err)
                embed.set_footer(text="Retrying in 1 minute")
                await channel.send(embed=embed)

            logger.warning("Chat relaying of Stream {} ended. Restart in 5 minute", self.vid_id)
            await asyncio.sleep(300)

            try:
                self.load_livechat()

            except Exception as err:
                logger.critical("Got {}.\nDetails: {}", type(err).__name__, err)
                await channel.send(embed=error_to_embed(err))
                return

    @command()
    async def stop_relay(self, context: Context):

        if context.author.id not in command_whitelist:
            await context.reply("Your user ID is not listed in whitelist.")
            logger.warning("User '{}' is not in whitelist.", context.author.display_name)

            return

        self.relay_task.stop()
        self.livechat.terminate()
        await context.reply("Stopped!")

    @command()
    async def change_stream_id(self, context: Context, video_id: str):

        logger.info("Called. Param: {}", video_id)

        if context.author.id not in command_whitelist:
            await context.reply("Your user ID is not listed in whitelist.")
            logger.warning("User '{}' is not in whitelist.", context.author.display_name)

            return

        try:
            self.relay_task.stop()
            self.load_livechat()
            self.relay_task.start()

        except Exception as err:
            message = f"Got {type(err).__name__}.\nDetails: {err}"
            logger.critical(message)

        else:
            message = "Reload complete!"

            config["yt_vid_id"] = video_id
            config_path.write_text(json.dumps(config))

        await context.reply(message)


# async def wrap():
#     async def callback(chatdata):
#         async for item in chatdata.async_items():
#             print("\n", item)
#             # print("\n".join(f"{m}: {getattr(item, m)}" for m in dir(item) if not m.startswith("__")))
#             print(json.dumps(json.loads(item.json()), indent=2))
#
#     stream = LiveChatAsync("UoGZuSayVuo", callback=callback)
#     while stream.is_alive():
#         await asyncio.sleep(3)
#
#
# asyncio.run(wrap())

__all__ = [
    CogRepresentation(YoutubeChatRelayCog)
]
