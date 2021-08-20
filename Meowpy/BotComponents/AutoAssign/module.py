"""
Auto assign module.

"""

import pathlib
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Union, Any, AsyncGenerator, Tuple, List

from discord.ext import tasks
from discord.ext.commands import Cog, Bot, Context
from discord import Embed, Member, Role, Guild, Message, Asset, errors, AllowedMentions
from loguru import logger

from .. import EventRepresentation, CogRepresentation, CommandRepresentation


# --------------------------------------
# Global Variable setup and Config loading

# config loading
config_path = pathlib.Path(__file__).parent.joinpath("config.json")
loaded_config = json.loads(config_path.read_text())

DB_PATH = pathlib.Path(__file__).parent.joinpath(loaded_config["db_path"])
SAVE_INTERVAL = loaded_config["save_interval_minute"]
OLDEST_TIMESTAMP = loaded_config["oldest_timestamp_check"]

# convert server settings key to number
SERVER_CONFIG = {int(key): val for key, val in loaded_config["server_settings"].items()}
NAME = __name__

# Test directory. If this fails Error will be caught from main bot so that's fine.
DB_PATH.mkdir(exist_ok=True)

# --------------------------------------


async def chat_history_gen(
    guild: Guild, from_date: Union[datetime, None], to_date: datetime
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


# --------------------------------------


def discord_stat_embed_gen(member: Member):
    try:
        role = member.top_role
    except AttributeError:
        role = None

    role: Union[Role, None]

    thumb: Asset = member.avatar_url

    embed = Embed(title=f"{member.display_name}", colour=role.color if role else None)

    now = datetime.utcnow()
    discord_join = now - member.created_at
    member_join = now - member.joined_at

    premium = (now - member.premium_since) if member.premium_since else None

    embed.add_field(
        name="Discord joined",
        value=f"{discord_join.days}d {discord_join.seconds // 3600}hr",
        inline=True,
    )
    embed.add_field(
        name="Server joined",
        value=f"{member_join.days}d {member_join.seconds // 3600}hr",
        inline=True,
    )

    if premium:
        embed.add_field(
            name="Boost for",
            value=f"{premium.days}d {premium.seconds // 3600}hr",
            inline=True,
        )

    if role:
        embed.set_footer(text=f"Primary role - {role.name}")

    embed.set_thumbnail(url=str(thumb))

    return embed


# --------------------------------------


def generate_congratulation_embed(
    member: Member, next_role: Role, delta: timedelta, count
):

    embed = Embed(title=f"{member.display_name}", colour=next_role.colour)

    embed.set_thumbnail(url=str(member.avatar_url))
    embed.add_field(name="Member for", value=f"{delta.days}d {delta.seconds // 3600}hr")
    embed.add_field(name=f"Messages sent", value=f"{count} times")

    return embed


# --------------------------------------


class TimeDeltaWrap:
    def __init__(self, time_delta: timedelta):
        self.delta = time_delta

    def __str__(self):
        if self.delta.days:
            return f"{self.delta.days} days"

        hour, seconds = divmod(self.delta.seconds, 3600)
        minute, seconds = divmod(seconds, 60)

        return f"{hour}h {minute}m {seconds}s"


# --------------------------------------


class DBWrapper:
    def __init__(self, db_path_):
        self.con = sqlite3.connect(db_path_)
        self.cursor = self.con.cursor()

        self.con.execute(
            "CREATE TABLE IF NOT EXISTS ACCUMULATION(user_id INTEGER PRIMARY KEY, counter INTEGER, access DOUBLE)"
        )

        self.con.commit()
        self.last_access = 1.0 if self.is_emtpy else self.get_last_timestamp()

    def count_up(self, message: Message):
        user_id = message.author.id
        timestamp = message.created_at.timestamp()

        if self.user_exists(user_id):
            self.con.execute(
                "UPDATE ACCUMULATION SET counter = counter + 1, access = ? WHERE user_id = ?",
                (timestamp, user_id),
            )
        else:
            self.con.execute(
                "INSERT INTO ACCUMULATION(user_id, counter, access) VALUES(?, ?, ?)",
                (user_id, 1, timestamp),
            )

        self.con.commit()

    def get_last_timestamp(self) -> float:

        self.cursor.execute("SELECT MAX(access) FROM ACCUMULATION")

        output = self.cursor.fetchone()[0]
        return output if output else 0

    def get_last_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.get_last_timestamp())

    def get_user_counter(self, user_id: int) -> int:
        if self.user_exists(user_id):
            self.cursor.execute(
                "SELECT counter FROM ACCUMULATION WHERE user_id = ?", (user_id,)
            )
            return self.cursor.fetchone()[0]

        return 0

    def user_exists(self, user_id: int) -> bool:

        self.cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM ACCUMULATION WHERE user_id = ?)", (user_id,)
        )

        return bool(self.cursor.fetchone()[0])

    def get_top_n(self, results=5) -> List[Tuple[int, int, float]]:

        self.cursor.execute(
            f"SELECT * FROM ACCUMULATION ORDER BY COUNTER DESC LIMIT {results}"
        )

        return self.cursor.fetchall()

    @property
    def is_emtpy(self) -> bool:

        self.cursor.execute("SELECT EXISTS(SELECT 1 FROM ACCUMULATION)")

        return not self.cursor.fetchone()[0]

    def close(self):
        self.__del__()

    def __del__(self):
        try:
            self.con.commit()
            self.con.close()
        except sqlite3.ProgrammingError:
            pass


# --------------------------------------


class DataHandler:
    dbs: Dict[int, DBWrapper] = {}
    catchup_running = False

    _server_ids = set(map(int, SERVER_CONFIG.keys()))
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

        try:
            target_server = cls.dbs[server_id]
        except KeyError:
            logger.warning(
                "[{}] Got message from unlisted server {}, ignoring.", NAME, server_id
            )
            return False

        target_server.count_up(message)

        return True

    @classmethod
    def load(cls):

        for server_id in cls._server_ids:
            path_ = DB_PATH.joinpath(f"{server_id}_counter").with_suffix(".db")
            cls.dbs[server_id] = DBWrapper(path_)

    @classmethod
    def close(cls):

        for server_id, db_ in cls.dbs.items():
            db_.close()

    @classmethod
    async def catch_up(cls, bot: Bot):
        # hold on, this will be really really expensive!

        if cls.catchup_running:
            return

        cls.catchup_running = True

        for server_id, db in cls.dbs.items():
            server: Guild = bot.get_guild(server_id)
            if server is None:
                logger.debug(
                    "[{}] Bot is not a part of server '{}', ignoring.", NAME, server_id
                )
                continue

            timestamp = db.get_last_timestamp()

            if not timestamp:
                time_ = server.created_at
            else:
                time_ = datetime.fromtimestamp(timestamp)

            logger.debug(
                "[{}] Catching up server '{}', from ts {}", NAME, server, timestamp
            )

            counter = 0
            iterator = chat_history_gen(server, time_, datetime.utcnow())

            try:
                first_msg = await iterator.__anext__()
            except StopAsyncIteration:
                pass
            else:

                # check if first message is already recorded
                if first_msg.created_at.timestamp() != db.get_last_timestamp():
                    logger.debug("Got timestamp diff, ")
                    counter += 1
                    DataHandler.count_up(first_msg)

                async for message in iterator:

                    # if message.created_at.timestamp() == timestamp:
                    #     continue

                    DataHandler.count_up(message)
                    counter += 1

            logger.debug("[{}] Fetched {} and added new messages.", NAME, counter)

        cls.catchup_running = False


# --------------------------------------


async def member_stat(context: Context, member_id: Union[Member, int] = 0):

    logger.info("called, param: {} type: {}", member_id, type(member_id))

    if not member_id:
        member: Member = context.author

    elif isinstance(member_id, Member):
        member = member_id
    else:
        member: Member = context.guild.get_member(member_id)

    if not member:
        await context.reply("No such member exists!")
        return

    embed = discord_stat_embed_gen(member)

    embed.add_field(
        name="Messages sent",
        value=f"{DataHandler.show_count(context.guild.id, member.id)}",
        inline=True,
    )

    try:
        await context.reply(embed=embed)
    except errors.Forbidden:
        logger.warning(
            "No permission to write to channel [{}] [ID {}].",
            context.channel.name,
            context.channel.id,
        )


async def on_message_trigger(message: Message):
    member: Member = message.author
    guild: Union[Guild, None, Any] = message.guild

    if member.bot:
        return

    try:
        assert DataHandler.count_up(message)
    except AttributeError:
        logger.warning(
            "[{}] Got a PM from {}, content: {}",
            NAME,
            member.display_name,
            message.content,
        )
        return
    except AssertionError:
        logger.warning(
            "[{}] Got a message from unlisted server {}, ignoring.", NAME, guild.id
        )
    except sqlite3.ProgrammingError:
        logger.warning("[{}] DB is closed, is this reloading?", NAME)
        return

    # server exists, then fetch config for faster access
    config = SERVER_CONFIG[guild.id]

    # check member age first
    diff = datetime.utcnow() - member.joined_at
    if diff.days < config["minimum_joined_days"]:
        return

    # then check if member is new member
    role_id = SERVER_CONFIG[guild.id]["from_role"]
    role = guild.get_role(role_id)

    if role not in member.roles:
        return

    # then check how much comment he made in server
    comments_count = DataHandler.show_count(guild.id, member.id)

    if comments_count < config["minimum_chats"]:
        return

    # if all good then promote the user.
    logger.info(
        "[{}] User '{}' (age: {}d, comments: {}) met requirements.",
        NAME,
        member.display_name,
        diff.days,
        comments_count,
    )

    # check if test mode is enabled.
    if config["test_mode"]:
        logger.info("[{}] Test mode enabled, will not actually affect roles.", NAME)
        return

    next_role = guild.get_role(config["new_role"])
    await member.remove_roles(role)
    await member.add_roles(next_role)

    if channel_id := config["notify_channel"]:
        channel = message.guild.get_channel(channel_id)

        await channel.send(
            f"Congratulation <@{member.id}>, you're now a {next_role.name}!",
            embed=generate_congratulation_embed(
                member, next_role, diff, comments_count
            ),
        )
        return

    await message.reply(
        f"Congratulation <@{member.id}>, you're now a {next_role.name}!",
        embed=generate_congratulation_embed(member, next_role, diff, comments_count),
    )


async def member_top(context: Context, results: int = 5):

    logger.info("called, param: {}", results)

    if results > 10:
        results = 10

    try:
        db = DataHandler.dbs[context.guild.id]
    except KeyError:
        logger.info("DB data for Server {} does not exists", context.guild.id)
        return

    member_list = db.get_top_n(results)
    embed = Embed(
        title=f"Highest message count top {results}",
        timestamp=context.message.created_at,
    )

    ranks = [str(n) for n in range(1, len(member_list) + 1)]
    top_ids = (f"<@{member_id}>" for member_id, _, _ in member_list)
    top_chats = (f"{chat}" for _, chat, _ in member_list)

    embed.add_field(name="Rank", value="\n".join(ranks))
    embed.add_field(name="Name", value="\n".join(top_ids))
    embed.add_field(name="Count", value="\n".join(top_chats))

    try:
        await context.reply(embed=embed, allowed_mentions=AllowedMentions(users=False))
    except errors.Forbidden:
        logger.warning(
            "No permission to write to channel [{}] [ID {}].",
            context.channel.name,
            context.channel.id,
        )


async def trigger_catchup(context: Context):

    logger.info("[{}] called", NAME)

    await DataHandler.catch_up(context.bot)


class AssignCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        # self.name = self.__class__.__name__

        logger.info("[AssignCog] starting.")
        self.callable_wrapper.start()

    def cog_unload(self):
        logger.info("[AssignCog] stopping.")
        DataHandler.close()

    @tasks.loop(count=1)
    async def callable_wrapper(self):

        logger.info("[AssignCog] Catching up missing accumulation.")
        await DataHandler.catch_up(self.bot)

        logger.info("[AssignCog] All loaded up!")
        DataHandler.prepared = True

    @callable_wrapper.before_loop
    async def load(self):
        logger.info("[AssignCog] Loading up stored data.")
        DataHandler.load()

    def __del__(self):
        DataHandler.close()


__all__ = [
    CogRepresentation(AssignCog),
    EventRepresentation(on_message_trigger, "on_message"),
    CommandRepresentation(
        member_stat, name="stat", help="Shows your stats in this server."
    ),
    CommandRepresentation(
        member_top, name="top", help="Shows top N member with most chat count."
    ),
    # CommandRepresentation(trigger_catchup, name="catchup", help="Manually triggers message catchup.")
]
