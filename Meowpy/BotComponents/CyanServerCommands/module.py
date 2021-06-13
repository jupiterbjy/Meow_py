import json
import pathlib
from datetime import datetime, timezone
from typing import Union, List

from dateutil.parser import isoparse
from discord.ext.commands import Context
from discord import Embed, Colour, File, Member, User, Role, Guild, Forbidden
from loguru import logger

from .youtube_api_client import GoogleClient
from .. import CommandRepresentation


google_api = ""
record_absolute_path = ""
subscription_role_id: int
yt_channels: List[str]

config_path = pathlib.Path(__file__).parent.joinpath("config.json")
loaded_config = json.loads(config_path.read_text())
locals().update(loaded_config)


async def run_literally(context: Context):
    logger.info("called by {}", context.author)

    await context.send(
        "https://cdn.discordapp.com/attachments/783069235999014912/840531297499480084/ezgif.com-gif-maker.gif"
    )


# --------------------------------------


async def get_stream_image(context: Context, index: int = 0):
    logger.info("called by {}, index {}", context.author, index)

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
    user: Union[Member, User] = context.author

    # get role
    guild: Guild = context.guild
    role: Role = guild.get_role(subscription_role_id)

    if role not in user.roles:
        await context.reply("You're not subscribed to live stream notification!")
        return

    try:
        await user.remove_roles(role, reason="Unsubscribing to live stream notification.")
    except Forbidden:
        await context.reply("I have no privilege to remove roles! Ask mods for help!")
    else:
        await context.reply("Unsubscribed from live stream notification!")


__all__ = [
    CommandRepresentation(run_literally, name="run", help="Run cyan run!"),
    CommandRepresentation(subscribe, name="sub", help="Subscribe to live stream notification"),
    CommandRepresentation(unsubscribe, name="unsub", help="Unsubscribe from live stream notification")
]

# Add if google api is provided
if google_api:
    __all__.append(
        CommandRepresentation(
            get_stream_image,
            name="streamgraph",
            help="Get stream's public statistics graph. "
                 "Due to check interval and http errors, file may either be incomplete or not graphed at all.",
            err_handler=get_stream_image_error,
        )
    )

# Add if path is provided
if record_absolute_path:
    record_path = pathlib.Path(record_absolute_path)

    if not record_path.exists():
        logger.critical("Given record path {} does not exist, skipping.", record_path.as_posix())

    else:
        __all__.append(
            CommandRepresentation(
                get_latest, name="latest", help="Shows latest uploaded video."
            )
        )
