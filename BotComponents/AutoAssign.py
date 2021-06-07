import pathlib
import json
from datetime import datetime, timedelta
from typing import Dict, Union, Any

from discord.ext import tasks
from discord.ext.commands import Cog, Bot, Context
from discord import Embed, Member, Role, Guild, Message, Asset
from loguru import logger

from . import EventRepresentation, CogRepresentation, CommandRepresentation


config_path = pathlib.Path(__file__).with_suffix(".json")
loaded_config = json.loads(config_path.read_text())

cache_path = pathlib.Path(__file__).parent.joinpath(loaded_config["cache_path"])
save_interval = loaded_config["save_interval_minute"]
oldest_timestamp_check = loaded_config["oldest_timestamp_check"]
server_settings: Dict[str, dict] = loaded_config["server_settings"]

# convert server settings key to number
server_settings = {int(key): val for key, val in server_settings.items()}


async def chat_history_gen(guild: Guild, from_date: datetime, to_date: datetime):

    for channel in guild.text_channels:

        message: Message
        async for message in channel.history(after=from_date, before=to_date):
            yield message


def generate_congratulation_embed(member: Member, next_role: Role, day, count):

    embed = Embed(title=f"{member.display_name}", colour=next_role.colour)

    embed.set_thumbnail(url=str(member.avatar_url))
    embed.add_field(name="Member for", value=f"{day} days")
    embed.add_field(
        name=f"Messages sent", value=f"{count} times"
    )

    return embed


class TimeDeltaWrap:
    def __init__(self, time_delta: timedelta):
        self.delta = time_delta

    def __str__(self):
        if self.delta.days:
            return f"{self.delta.days} days"

        hour, seconds = divmod(self.delta.seconds, 3600)
        minute, seconds = divmod(seconds, 60)

        return f"{hour}h {minute}m {seconds}s"


class JsonDataHandler:
    _server_data = {}
    _server_ids = set(map(int, server_settings.keys()))
    _server_data_paths = {}
    prepared = False

    @classmethod
    def show_count(cls, server_id, user_id) -> int:
        return cls._server_data[server_id]["data"][user_id]

    @classmethod
    def count_up(cls, message: Message) -> bool:
        """
        Counts up given server and user. Will ignore servers not listed in json config.

        :return: True if server entry exists, false if not.
        """

        server_id = message.guild.id
        user_id = message.author.id

        try:
            target_server = cls._server_data[server_id]
        except KeyError:
            logger.warning("Got message from unlisted server {}, ignoring.", server_id)
            return False

        try:
            target_server["data"][user_id] += 1
        except KeyError:
            target_server["data"][user_id] = 1

        target_server["timestamp"] = message.created_at

        return True

    @classmethod
    def load(cls):

        for server_id in cls._server_ids:
            logger.debug("Checking server {} data.", server_id)

            path_ = cache_path.joinpath(f"{server_id}_counter").with_suffix(".json")
            cls._server_data_paths[server_id] = path_

            temporary_dict = {"timestamp": oldest_timestamp_check, "data": {}}

            try:
                path_.touch(exist_ok=False)

            except PermissionError:
                logger.critical("No permission to touch at {}.\n"
                                "Change directory/file's permission or data won't be saved on exit!", cache_path)
            except FileExistsError:
                logger.debug("Previous data found. Attempting to load.")

                try:
                    loaded = json.loads(path_.read_text())
                except Exception as err_:
                    logger.critical("Failed to load {}.\nFile may get overwritten afterward!\nReason: {}", path_, err_)
                else:
                    loaded["data"] = {int(k): v for k, v in loaded["data"].items()}
                    temporary_dict = loaded
            else:
                logger.info("Creating new empty record for server {}.", server_id)

            cls._server_data[server_id] = temporary_dict

    @classmethod
    def write(cls):

        if not cls._server_data:
            return

        for server_id, path_ in cls._server_data_paths.items():
            path_: pathlib.Path

            if not cls._server_data[server_id]["data"]:
                logger.info("No data in {}, skipping write.", server_id)
                continue

            target = cls._server_data[server_id]

            try:
                path_.write_text(json.dumps(target))

            except PermissionError:
                logger.critical("No permission to write at {}.\n"
                                "Change directory/file's permission or data won't be saved on exit!", cache_path)

            except Exception as err_:
                logger.critical("Unknown Error occurred.\nDetail:{}", err_)

            else:
                logger.info("Record for server {} written.", server_id)

    @classmethod
    async def catch_up(cls, bot: Bot):
        # hold on, this will be really really expensive!

        for server_id in cls._server_ids:
            server: Guild = bot.get_guild(server_id)

            if server is None:
                logger.debug("Bot is not a part of server '{}', ignoring.", server_id)
                continue

            timestamp = cls._server_data[server_id]["timestamp"]

            logger.debug("Catching up server '{}', ts {}", server, timestamp)

            # get each server's catchup times

            # already timestamp is set to utc(past), it will loose yet another offset
            time_ = datetime.fromtimestamp(timestamp) if timestamp else server.created_at

            counter = 0
            async for message in chat_history_gen(server, time_, cls._loaded_time):
                JsonDataHandler.count_up(message)
                counter += 1

            logger.debug("Fetched {} and added new messages.", counter)

    _loaded_time = datetime.utcnow()


async def debug_data(context: Context):
    await context.reply(f"```json\n{json.dumps(JsonDataHandler._server_data, indent=2)}\n```")


async def member_stat(context: Context):

    logger.info("called")
    member: Member = context.author

    role: Role = member.top_role

    thumb: Asset = member.avatar_url

    embed = Embed(title=f"{member.display_name}", colour=role.color)

    now = datetime.utcnow()
    discord_join = TimeDeltaWrap(now - member.created_at)
    member_join = TimeDeltaWrap(now - member.joined_at)

    premium = (
        TimeDeltaWrap(now - member.premium_since) if member.premium_since else None
    )

    embed.add_field(name="Discord joined", value=f"{discord_join}")

    embed.add_field(name="Server joined", value=f"{member_join}")

    if premium:
        embed.add_field(name="Boost since", value=f"{premium}")

    embed.add_field(name="Messages sent", value=f"{JsonDataHandler.show_count(context.guild.id, member.id)}")

    embed.set_footer(text=f"Primary role - {role.name}")
    embed.set_thumbnail(url=str(thumb))

    await context.reply(embed=embed)


async def on_message_trigger(message: Message):
    member: Member = message.author
    guild: Union[Guild, None, Any] = message.guild

    if member.bot:
        return

    try:
        assert JsonDataHandler.count_up(message)
    except AttributeError:
        logger.warning("Got a PM from {}, content: {}", member.display_name, message.content)
        return
    except AssertionError:
        logger.warning("Got a message from unlisted server {}, ignoring.", guild.id)

    # server exists, then fetch config for faster access
    config = server_settings[guild.id]

    # check member age first
    if (day := (datetime.utcnow() - member.joined_at).days) < config["minimum_joined_days"]:
        return

    # then check if member is new member
    role_id = server_settings[guild.id]["from_role"]
    role = guild.get_role(role_id)

    if role not in member.roles:
        return

    # then check how much comment he made in server
    comments_count = JsonDataHandler.show_count(guild.id, member.id)

    if comments_count < config["minimum_chats"]:
        return

    # if all good then promote the user.
    next_role = guild.get_role(config["new_role"])
    await member.remove_roles(role)
    await member.add_roles(next_role)

    await message.reply(
        f"Congratulation <@{member.id}>, you're now a {next_role.name}!",
        embed=generate_congratulation_embed(member, next_role, day, comments_count),
    )


class AssignCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        logger.info("[AssignCog] starting.")
        self.callable_wrapper.start()
        self.task.start()

    def cog_unload(self):
        logger.info("[AssignCog] stopping.")
        self.task.cancel()
        JsonDataHandler.write()

    @tasks.loop(count=1)
    async def callable_wrapper(self):

        logger.info("[AssignCog] Catching up missing accumulation.")
        await JsonDataHandler.catch_up(self.bot)

        logger.info("[AssignCog] All loaded up!")
        JsonDataHandler.prepared = True

    @callable_wrapper.before_loop
    async def load(self):
        logger.info("[AssignCog] Loading up stored data.")
        JsonDataHandler.load()

    @tasks.loop(minutes=save_interval)
    async def task(self):
        if JsonDataHandler.prepared:
            logger.info("[AssignCog] saving comment accumulation.")
            JsonDataHandler.write()

    def __del__(self):
        logger.info("[AssignCog] saving comment accumulation.")
        JsonDataHandler.write()


__all__ = [
    CogRepresentation(AssignCog),
    EventRepresentation(on_message_trigger, "on_message"),
    CommandRepresentation(member_stat, name="stat", help="Shows your stats in this server."),
    CommandRepresentation(debug_data, name="debug_data", help="in pain")
]
