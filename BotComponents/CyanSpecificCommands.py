import json
import pathlib
from datetime import datetime, timezone

from dateutil.parser import isoparse
from discord.ext.commands import Context
from discord import Embed, Colour, File
from loguru import logger

from youtube_api_client import GoogleClient
from . import CommandRepresentation


config_path = pathlib.Path(__file__).with_suffix(".json")
loaded_config = json.loads(config_path.read_text())

google_api_key = loaded_config["google_api"]
path_designated = loaded_config["record_absolute_path"]


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

    client = GoogleClient(google_api_key)

    stat_less_main = client.get_latest_videos("UC9wbdkwvYVSgKtOZ3Oov98g", 1)[0]
    stat_less_sub = client.get_latest_videos("UC9waeFu44i5NwB7x48Tq6Bw", 1)[0]

    latest = (
        stat_less_sub
        if stat_less_main.pub_date < stat_less_sub.pub_date
        else stat_less_main
    )

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

    embed.set_image(url=new_.thumbnail_url(4))
    embed.set_footer(text=diff_str)

    await context.reply(embed=embed)


__all__ = [CommandRepresentation(run_literally, name="run", help="Run cyan run!")]

# Add if google api is provided
if google_api_key:
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
if path_designated:
    record_path = pathlib.Path(path_designated)

    if not record_path.exists():
        logger.critical("Given record path {} does not exist, skipping.", record_path.as_posix())

    else:
        __all__.append(
            CommandRepresentation(
                get_latest, name="latest", help="Shows latest uploaded video."
            )
        )
