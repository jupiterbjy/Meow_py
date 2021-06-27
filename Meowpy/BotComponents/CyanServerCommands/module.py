import json
import pathlib
from datetime import datetime, timezone
from typing import Union, List

from dateutil.parser import isoparse
from discord.ext.commands import Context, Cog, Bot, command
from discord.ext import tasks
from discord import (
    Embed,
    Colour,
    File,
    Member,
    User,
    Role,
    Guild,
    Forbidden,
    TextChannel,
)
from loguru import logger

from .youtube_api_client import GoogleClient
from .. import CommandRepresentation, CogRepresentation


google_api = ""
record_absolute_path = ""
subscription_role_id: int = 0
yt_channels: List[str]

config_path = pathlib.Path(__file__).parent.joinpath("config.json")
loaded_config = json.loads(config_path.read_text())
locals().update(loaded_config)


async def run_literally(context: Context):
    logger.info("called by {}", context.author.id)

    await context.send(
        "https://cdn.discordapp.com/attachments/783069235999014912/840531297499480084/ezgif.com-gif-maker.gif"
    )


# --------------------------------------


async def get_stream_image(context: Context, index: int = 0):
    logger.info("called by {}, index {}", context.author.id, index)

    files = [f for f in record_path.iterdir() if f.suffix == ".png"]

    sorted_files = sorted(files, reverse=True)

    try:
        target = sorted_files[index]
    except IndexError:
        index = len(sorted_files) - 1
        target = sorted_files[index]

    target_json = target.with_suffix(".json")
    loaded_json = json.loads(target_json.read_text())

    date, timestamp, video_id = target.stem.split("_", 2)
    link = f"https://youtu.be/{video_id}"

    with open(target, "rb") as fp:
        file = File(fp, f"{timestamp}.png")

    embed = Embed(
        title=f"Stream at {timestamp} epoch time",
        description=link,
        colour=Colour.from_rgb(24, 255, 255),
    )

    embed.add_field(
        name="Stream title", value=loaded_json["stream_title"], inline=False
    )

    embed.add_field(
        name="Sample count / interval",
        value=f"{len(loaded_json['data']['viewCount'])} / {loaded_json['interval']}",
    )

    embed.set_image(url=f"attachment://{timestamp}.png")
    embed.set_thumbnail(url=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg")

    await context.reply(file=file, embed=embed)


# --------------------------------------


async def get_stream_image_error(context: Context, _):
    await context.reply("You passed wrong parameter! Value should be integer!")


# --------------------------------------


async def get_latest(context: Context):

    logger.info("called by {}", context.author.id)

    client = GoogleClient(google_api)

    vid_infos = [client.get_latest_videos(id_, 1)[0] for id_ in yt_channels]

    latest = sorted(vid_infos, key=lambda x: x.pub_date)[-1]

    new_ = client.get_videos_info(latest.video_id)[0]

    diff = datetime.now(timezone.utc) - isoparse(new_.published_at)

    if diff.days:
        diff_str = f"Uploaded {diff.days} day(s) ago."
    else:
        diff_str = (
            f"Uploaded {diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m ago."
        )

    embed = Embed(
        title=new_.title,
        description=new_.description.strip().split("\n")[0],
        colour=Colour.from_rgb(24, 255, 255),
    )

    embed.add_field(name="Views", value=f"{new_.view_count}")
    embed.add_field(name="Likes", value=f"{new_.like_count}", inline=True)
    embed.add_field(name="Link", value=f"https://youtu.be/{new_.video_id}")

    embed.set_image(url=new_.thumbnail_url(4))
    embed.set_footer(text=diff_str)

    await context.reply(embed=embed)


# --------------------------------------


async def subscribe(context: Context):

    logger.info("called by {}", context.author.id)

    user: Union[Member, User] = context.author

    # get role
    guild: Guild = context.guild
    role = guild.get_role(subscription_role_id)

    if role in user.roles:
        await context.reply("You're already subscribed to live stream notification!")
        return

    try:
        await user.add_roles(role, reason="Subscribing to live stream notification.")
    except Forbidden:
        await context.reply("I have no privilege to assign roles! Ask mods for help!")
    else:
        await context.reply("Subscribed to live stream notification!")


# --------------------------------------


async def unsubscribe(context: Context):

    logger.info("called by {}", context.author.id)

    user: Union[Member, User] = context.author

    # get role
    guild: Guild = context.guild
    role: Role = guild.get_role(subscription_role_id)

    if role not in user.roles:
        await context.reply("You're not subscribed to live stream notification!")
        return

    try:
        await user.remove_roles(
            role, reason="Unsubscribing to live stream notification."
        )
    except Forbidden:
        await context.reply("I have no privilege to remove roles! Ask mods for help!")
    else:
        await context.reply("Unsubscribed from live stream notification!")


# --------------------------------------


class CheckSubscribersCount(Cog):
    div_factor = 1000

    def __init__(self, bot: Bot):
        logger.info("[CheckSub] Starting.")

        self.bot = bot
        self.channel_id = yt_channels[0]
        self.client = GoogleClient(google_api)
        self.last_sub = self.get_subs()
        self.last_sub_factor = self.last_sub // self.div_factor

        self.task.start()

    def get_subs(self) -> int:
        return self.client.get_subscribers_count(self.channel_id)

    def cog_unload(self):
        logger.info("[CheckSub] Stopping.")
        self.task.stop()

    @tasks.loop(seconds=15)
    async def task(self):
        self.last_sub = self.get_subs()

        factor = self.last_sub // self.div_factor

        if factor > self.last_sub_factor:
            self.last_sub_factor = factor

            message = Embed(title=f"{factor * self.div_factor} reached!")

            message.add_field(name="Subscribers", value=f"{self.last_sub}")

            message.set_thumbnail(
                url="https://cdn.discordapp.com/avatars/757307928012259419/cfce0470f52118f947b93eb78f2033f9.webp?size=1024"
            )

            target_server: Guild = self.bot.get_guild(757313446730793101)
            target_channel: TextChannel = target_server.get_channel(854206017147371541)

            await target_channel.send(embed=message)

    @command()
    async def subs(self, context: Context):

        logger.info("called by {}", context.author.id)

        await context.reply(f"Last reported subscribers: {self.last_sub}")

    @command()
    async def check_sub_debug(self, context: Context):

        logger.info("called by {}", context.author.id)

        message = Embed(title=f"Debug data for {type(self).__name__}")

        string_key = f"channel_id\nlast_sub\nlast_sub_factor\ndiv_factor"
        string_val = f"{self.channel_id}\n{self.last_sub}\n{self.last_sub_factor}\n{self.div_factor}"

        message.add_field(name="Key", value=string_key)
        message.add_field(name="Value", value=string_val)

        await context.reply(embed=message)


__all__ = [
    CommandRepresentation(run_literally, name="run", help="Run cyan run!"),
]

if subscription_role_id:
    __all__.extend(
        (
            CommandRepresentation(
                subscribe, name="sub", help="Subscribe to live stream notification"
            ),
            CommandRepresentation(
                unsubscribe,
                name="unsub",
                help="Unsubscribe from live stream notification",
            ),
        )
    )

# Add if google api is provided
if google_api:
    __all__.append(
        CommandRepresentation(
            get_stream_image,
            name="streamgraph",
            help="Get stream's public statistics graph."
            "Due to check interval and http errors, file may either be incomplete or not graphed at all.",
            err_handler=get_stream_image_error,
        )
    )

    __all__.append(CogRepresentation(CheckSubscribersCount))

# Add if path is provided
if record_absolute_path:
    record_path = pathlib.Path(record_absolute_path)

    if not record_path.exists():
        logger.critical(
            "Given record path {} does not exist, skipping.", record_path.as_posix()
        )

    else:
        __all__.append(
            CommandRepresentation(
                get_latest, name="latest", help="Shows latest uploaded video."
            )
        )
