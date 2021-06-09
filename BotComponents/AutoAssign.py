import pathlib
import json
import sqlite3
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


async def chat_history_gen(
    guild: Guild, from_date: Union[datetime, None], to_date: datetime
):

    for channel in guild.text_channels:

        message: Message
        async for message in channel.history(after=from_date, before=to_date):
            yield message


def generate_congratulation_embed(member: Member, next_role: Role, day, count):

    embed = Embed(title=f"{member.display_name}", colour=next_role.colour)

    embed.set_thumbnail(url=str(member.avatar_url))
    embed.add_field(name="Member for", value=f"{day} days")
    embed.add_field(name=f"Messages sent", value=f"{count} times")

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


class DBWrapper:
    def __init__(self, db_path):
        self.con = sqlite3.connect(db_path)
        self.cursor = self.con.cursor()

        self.con.execute(
            "CREATE TABLE IF NOT EXISTS ACCUMULATION(user_id INTEGER PRIMARY KEY, counter INTEGER, access DOUBLE)"
        )

        self.last_access = 1.0 if self.is_emtpy else self.get_last_access()

    def count_up(self, message: Message):
        user_id = message.author.id

        if self.user_exists(user_id):
            self.con.execute(
                "UPDATE ACCUMULATION SET counter = counter + 1, access = ? WHERE ?",
                (message.created_at.timestamp(), user_id),
            )
        else:
            self.con.execute(
                "INSERT INTO ACCUMULATION(user_id, counter, access) VALUES(?, ?, ?)",
                (user_id, 1, message.created_at.timestamp())
            )

    def get_last_access(self) -> Union[float, None]:

        self.cursor.execute("SELECT MAX(access) FROM ACCUMULATION")

        return self.cursor.fetchone()[0]

    def get_user_counter(self, user_id: int) -> int:
        if self.user_exists(user_id):
            self.cursor.execute("SELECT counter FROM ACCUMULATION WHERE ?", (user_id,))
            return self.cursor.fetchone()[0]

        return 0

    def user_exists(self, user_id: int) -> bool:

        self.cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM ACCUMULATION WHERE user_id=?)", (user_id,)
        )

        return bool(self.cursor.fetchone()[0])

    @property
    def is_emtpy(self) -> bool:

        self.cursor.execute("SELECT EXISTS(SELECT 1 FROM ACCUMULATION)")

        return not self.cursor.fetchone()[0]

    def flush(self):
        self.con.commit()

    def __del__(self):
        self.con.close()


class DataHandler:
    dbs: Dict[int, DBWrapper] = {}

    _server_ids = set(map(int, server_settings.keys()))
    prepared = False

    @classmethod
    def show_count(cls, server_id, user_id) -> int:
        return cls.dbs[server_id].get_user_counter(user_id)

    @classmethod
    def count_up(cls, message: Message) -> bool:
        """
        Counts up given server and user. Will ignore servers not listed in json config.

        :return: True if server entry exists, false if not.
        """

        server_id = message.guild.id
        user_id = message.author.id

        try:
            target_server = cls.dbs[server_id]
        except KeyError:
            logger.warning("Got message from unlisted server {}, ignoring.", server_id)
            return False

        target_server.count_up(user_id)

        return True

    @classmethod
    def load(cls):

        for server_id in cls._server_ids:
            path_ = cache_path.joinpath(f"{server_id}_counter").with_suffix(".db")
            cls.dbs[server_id] = DBWrapper(path_)

    @classmethod
    def write(cls):

        for server_id, db_ in cls.dbs.items():
            db_.flush()

    @classmethod
    async def catch_up(cls, bot: Bot, start_time):
        # hold on, this will be really really expensive!

        for server_id, db in cls.dbs.items():
            server: Guild = bot.get_guild(server_id)

            if server is None:
                logger.debug("Bot is not a part of server '{}', ignoring.", server_id)
                continue

            timestamp = db.get_last_access()

            if timestamp:
                logger.debug("Catching up server '{}', from ts {}", server, timestamp)

                # already timestamp is set to utc(past), no need for utc
                time_ = (
                    datetime.fromtimestamp(timestamp) if timestamp else server.created_at
                )
            else:
                logger.debug("Catching up server '{}', from oldest history.", server)
                time_ = None

            counter = 0
            async for message in chat_history_gen(server, time_, start_time):
                DataHandler.count_up(message)
                counter += 1

            logger.debug("Fetched {} and added new messages.", counter)


# async def debug_data(context: Context):
#     await context.reply(f"```json\n{json.dumps(JsonDataHandler._server_data, indent=2)}\n```")


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

    embed.add_field(
        name="Messages sent",
        value=f"{DataHandler.show_count(context.guild.id, member.id)}",
    )

    embed.set_footer(text=f"Primary role - {role.name}")
    embed.set_thumbnail(url=str(thumb))

    await context.reply(embed=embed)


async def on_message_trigger(message: Message):
    member: Member = message.author
    guild: Union[Guild, None, Any] = message.guild

    if member.bot:
        return

    try:
        assert DataHandler.count_up(message)
    except AttributeError:
        logger.warning(
            "Got a PM from {}, content: {}", member.display_name, message.content
        )
        return
    except AssertionError:
        logger.warning("Got a message from unlisted server {}, ignoring.", guild.id)

    # server exists, then fetch config for faster access
    config = server_settings[guild.id]

    # check member age first
    if (day := (datetime.utcnow() - member.joined_at).days) < config[
        "minimum_joined_days"
    ]:
        return

    # then check if member is new member
    role_id = server_settings[guild.id]["from_role"]
    role = guild.get_role(role_id)

    if role not in member.roles:
        return

    # then check how much comment he made in server
    comments_count = DataHandler.show_count(guild.id, member.id)

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
        DataHandler.write()

    @tasks.loop(count=1)
    async def callable_wrapper(self):

        logger.info("[AssignCog] Catching up missing accumulation.")
        await DataHandler.catch_up(self.bot, datetime.utcnow())

        logger.info("[AssignCog] All loaded up!")
        DataHandler.prepared = True

    @callable_wrapper.before_loop
    async def load(self):
        logger.info("[AssignCog] Loading up stored data.")
        DataHandler.load()

    @tasks.loop(minutes=save_interval)
    async def task(self):
        if DataHandler.prepared:
            logger.info("[AssignCog] saving comment accumulation.")
            DataHandler.write()

    def __del__(self):
        logger.info("[AssignCog] saving comment accumulation.")
        DataHandler.write()


__all__ = [
    CogRepresentation(AssignCog),
    EventRepresentation(on_message_trigger, "on_message"),
    CommandRepresentation(
        member_stat, name="stat", help="Shows your stats in this server."
    ),
    # CommandRepresentation(debug_data, name="debug_data", help="in pain")
]
