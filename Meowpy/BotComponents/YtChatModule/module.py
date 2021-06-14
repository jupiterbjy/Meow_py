import asyncio
import pathlib
import json
from datetime import datetime
from typing import Dict, Union

import pytz
from pytchat import LiveChatAsync
from pytchat.processors.default.processor import Chatdata, Chat
from discord.ext.commands import Cog, Bot
from discord.ext import tasks
from discord.embeds import EmptyEmbed
from discord import Embed, TextChannel
from loguru import logger


from .. import CogRepresentation


config_path = pathlib.Path(__file__).parent.joinpath("config.json")
config: Dict[str, Union[str, int]] = json.loads(config_path.read_text())

yt_vid_id: str
discord_ch_id: int
interval_sec: int
timezone_str: str
role_symbol: Dict[str, str]
emoji_mapping: Dict[str, str]

locals().update(config)


def argb_to_rgb(argb: int):
    # what a mess..
    if not argb:
        return 0

    # converting int to hex string, strip 0x, zfill to 8 width argb, strip a.
    return int(hex(argb)[2:].zfill(8)[2:], base=16)


class YoutubeChatRelayCog(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot

        logger.info("[ChatRelay] starting.")

        self.run_flag = True
        self.relay_task.start()

    def cog_unload(self):
        logger.info("[ChatRelay] Stopping.")

        self.run_flag = False

    async def callback(self, chat_data: Chatdata):
        async for chat in chat_data.async_items():
            chat: Chat

            json_data: dict = json.loads(chat.json())

            logger.debug(f"Received json: \n{json.dumps(json_data, indent=2)}\n")

            author_dict: dict = json_data["author"]
            is_owner: bool = author_dict["isChatOwner"]
            is_mod: bool = author_dict["isChatModerator"]
            is_member: bool = author_dict["isChatSponsor"]

            type_: str = json_data["type"]
            message: str = json_data["message"]

            for yt_emoji, dc_image in emoji_mapping.items():
                if yt_emoji in message:
                    message = message.replace(yt_emoji, dc_image)

            donation_str: str = json_data["amountString"]

            bg_color: int = argb_to_rgb(json_data["bgColor"])

            # Start writing embed
            embed = Embed(title=donation_str if donation_str else EmptyEmbed, description=message, colour=bg_color)

            # prep icon
            icon = url if (url := author_dict["imageUrl"]) else EmptyEmbed

            # checks condition by order of Owner, Mod, Sponsor.
            if is_owner:
                role = "owner"
            elif is_mod:
                role = "moderator"
            elif is_member:
                role = "member"
            else:
                role = "default"

            name = " ".join((author_dict["name"], role_symbol[role]))

            embed.set_author(name=name, url=author_dict["channelUrl"], icon_url=icon)

            # check sticker
            if type_ == "superSticker":
                embed.set_thumbnail(url=json_data["sticker"])

            # set utc time
            timestamp = json_data["timestamp"] / 1000.0
            # try:
            #     utc_aware = datetime.fromtimestamp(timestamp, pytz.timezone(timezone_str))
            # except pytz.exceptions.UnknownTimeZoneError:
            #     logger.critical("Wrong timezone format!")
            #     return

            embed.timestamp = datetime.utcfromtimestamp(timestamp)
            # embed.set_footer(text=f"{utc_aware.strftime(type_ + ' %Y-%m-%d %H:%M:%S (UTC)')}")

            channel: TextChannel = self.bot.get_channel(discord_ch_id)
            try:
                await channel.send(embed=embed)
            except AttributeError:
                logger.critical("Unknown channel ID {}, check configuration!", discord_ch_id)

    @tasks.loop(count=1)
    async def relay_task(self):
        stream = LiveChatAsync(yt_vid_id, callback=self.callback)

        while stream.is_alive() and self.run_flag:
            await asyncio.sleep(3)

        if not self.run_flag:
            logger.info("Stopping task!")
        else:
            logger.warning("Stream {} stopped?", yt_vid_id)


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
