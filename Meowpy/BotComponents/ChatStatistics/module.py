"""
Hourly chat statistics module.

Creates DB for each server, and saves each channel as separate table
"""

import pathlib
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from discord import Message, Object, TextChannel, errors
from discord.ext import tasks
from discord.ext.commands import Bot, Cog, Context
from loguru import logger

from .. import CogRepresentation, CommandRepresentation, EventRepresentation


# --- Config ---

NAME = __name__

DB_PATH = pathlib.Path(__file__).parent / "dbs"
DB_PATH.mkdir(exist_ok=True)


# --- Util ---

def get_message_window(message: Message) -> int:
    """Returns unix timestamp of the hour window the message was sent in."""

    created_at: datetime = message.created_at

    # old discord.py naive dt workaround
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return int(created_at.timestamp()) // 3600 * 3600


class ChannelDB:
    """DB for per channel chat hourly statistics"""

    _sql_create_table: str = """
    CREATE TABLE IF NOT EXISTS "ch_{}" (
        unix_hour INTEGER PRIMARY KEY,
        msg_count INTEGER NOT NULL DEFAULT 0
    )
    """

    _sql_create_meta: str = """
    CREATE TABLE IF NOT EXISTS channel_meta (
        channel_id INTEGER PRIMARY KEY,
        last_message_id INTEGER NOT NULL
    )
    """

    _sql_last_message_id: str = """
    SELECT last_message_id FROM channel_meta WHERE channel_id = ?
    """

    _sql_set_last_message_id: str = """
    INSERT INTO channel_meta (channel_id, last_message_id) VALUES (?, ?)
    ON CONFLICT(channel_id) DO UPDATE SET last_message_id = excluded.last_message_id
    """

    _sql_count_up: str = """
    INSERT INTO "ch_{}" (unix_hour, msg_count) VALUES (?, 1)
    ON CONFLICT(unix_hour) DO UPDATE SET msg_count = msg_count + 1
    """

    _sql_get_all: str = """
    SELECT * FROM "ch_{}"
    """

    _sql_get_range: str = """
    SELECT unix_hour, msg_count FROM "ch_{}"
    WHERE unix_hour >= ? AND unix_hour < ? ORDER BY unix_hour
    """

    _sql_count_range: str = """
    SELECT SUM(msg_count) FROM "ch_{}"
    WHERE unix_hour >= ? AND unix_hour < ?
    """

    _sql_count_total: str = """
    SELECT SUM(msg_count) FROM "ch_{}"
    """

    RECORD = tuple[int, int]

    def __init__(self, db_path: pathlib.Path):
        self.conn = sqlite3.connect(db_path)
        self.table_name_cache = set()
        self.last_id_cache: Dict[int, int] = {}

        self.conn.execute(self._sql_create_meta)
        self.conn.commit()

    def ensure_table(self, ch_id: int):
        table = f"ch_{ch_id}"

        if table not in self.table_name_cache:
            self.conn.execute(self._sql_create_table.format(ch_id))
            self.conn.commit()

            self.table_name_cache.add(table)

    def get_last_message_id(self, ch_id: int) -> Optional[int]:
        """Returns last counted message ID of given channel, if any."""

        try:
            return self.last_id_cache[ch_id]

        except KeyError:
            row = self.conn.execute(self._sql_last_message_id, (ch_id,)).fetchone()

        if row is None:
            return None

        self.last_id_cache[ch_id] = row[0]
        return row[0]

    def count_up(self, ch_id: int, unix_hour: int, message_id: int) -> bool:
        """Count 1 message up for given unix hour window.

        Messages at or before the last counted message ID are ignored, making
        catch-up and duplicated events idempotent.
        """

        last_id = self.get_last_message_id(ch_id)

        if last_id is not None and message_id <= last_id:
            return False

        self.ensure_table(ch_id)
        self.conn.execute(self._sql_count_up.format(ch_id), (unix_hour,))
        self.conn.execute(self._sql_set_last_message_id, (ch_id, message_id))
        self.conn.commit()

        self.last_id_cache[ch_id] = message_id
        return True

    def reset_channel(self, ch_id: int):
        """Drops all data of given channel. Used to migrate legacy DBs."""

        table = f"ch_{ch_id}"

        self.conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        self.conn.execute("DELETE FROM channel_meta WHERE channel_id = ?", (ch_id,))
        self.conn.commit()

        self.table_name_cache.discard(table)
        self.last_id_cache.pop(ch_id, None)

    def get_record_range(
        self,
        ch_id: int,
        from_unix_t: int,
        to_unix_t: int,
    ) -> List[RECORD]:
        """Returns records for given range

        Returns:
            [(unix_time, msg_count), ...]
        """

        self.ensure_table(ch_id)
        cur = self.conn.execute(self._sql_get_range.format(ch_id), (from_unix_t, to_unix_t))
        return cur.fetchall()

    def get_record_all(self, ch_id: int) -> List[RECORD]:
        """Returns records for given range
        Returns:
            [(unix_time, msg_count), ...]
        """

        self.ensure_table(ch_id)
        return self.conn.execute(self._sql_get_all.format(ch_id)).fetchall()

    def get_count_range(
        self,
        ch_id: int,
        from_unix_t: int,
        to_unix_t: int,
    ) -> int:
        """Returns message count for given unix hour window"""

        self.ensure_table(ch_id)

        return (
            self.conn.execute(
                self._sql_count_range.format(ch_id),
                (from_unix_t, to_unix_t),
            ).fetchone()[0]
            or 0
        )

    def get_count_all(self, ch_id: int) -> int:
        """Returns message count for given unix hour window"""

        self.ensure_table(ch_id)
        return (
            self.conn.execute(self._sql_count_total.format(ch_id)).fetchone()[0]
            or 0
        )

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except (sqlite3.ProgrammingError, AttributeError):
            pass


# --- Logic ---

class DataHandler:
    _dbs: Dict[int, ChannelDB] = {}

    catchup_running = False
    _pending: List[Message] = []

    @classmethod
    def get_db(cls, guild_id: int) -> ChannelDB:
        """Fetches guild database, creating it on first access."""

        try:
            return cls._dbs[guild_id]

        except KeyError:
            db = ChannelDB(DB_PATH / f"{guild_id}.sqlite")
            cls._dbs[guild_id] = db

            logger.debug("[{}] Created database for server {}.", NAME, guild_id)
            return db

    @classmethod
    def _count_up_now(cls, message: Message) -> bool:
        if message.guild is None:
            return False

        return cls.get_db(message.guild.id).count_up(
            message.channel.id,
            get_message_window(message),
            message.id,
        )

    @classmethod
    def count_up(cls, message: Message) -> bool:
        """Counts message for its guild, channel and hour window.

        While catch-up is running, messages are buffered and counted after it
        finishes so history scans and live events don't double count.

        Returns:
            True if handled or buffered, False otherwise (DM)
        """

        if cls.catchup_running:
            cls._pending.append(message)
            return True

        return cls._count_up_now(message)

    @classmethod
    def flush_pending(cls):
        """Counts messages received while catch-up was running."""

        pending, cls._pending = cls._pending, []

        for message in pending:
            try:
                cls._count_up_now(message)
            except sqlite3.Error:
                logger.exception(
                    "[{}] Failed to count buffered message {}", NAME, message.id
                )

    @classmethod
    async def catch_up(cls, bot: Bot):
        """Backfills every readable channel, resuming from the last message ID."""

        if cls.catchup_running:
            return

        cls.catchup_running = True
        logger.info("[{}] Catching up chat statistics.", NAME)

        # rip indents
        try:
            for guild in bot.guilds:
                db = cls.get_db(guild.id)

                for channel in guild.text_channels:
                    try:
                        await cls._catch_up_channel(db, channel)

                    except errors.Forbidden:
                        logger.warning(
                            "[{}] Cannot access channel '{}' - ID: {}",
                            NAME,
                            channel.name,
                            channel.id,
                        )

                    except errors.HTTPException as err:
                        logger.warning(
                            "[{}] Failed to fetch history of channel '{}' - ID: {} ({})",
                            NAME,
                            channel.name,
                            channel.id,
                            err,
                        )

                    except Exception as err:
                        logger.exception(
                            "[{}] Failed to catch up channel '{}' - ID: {} ({})",
                            NAME,
                            channel.name,
                            channel.id,
                            err
                        )

        finally:
            cls.flush_pending()
            cls.catchup_running = False

    @classmethod
    async def _catch_up_channel(cls, db: ChannelDB, channel: TextChannel):
        last_id = db.get_last_message_id(channel.id)

        if last_id is None:
            # No cursor yet (new or legacy DB): rebuild from full history.
            db.reset_channel(channel.id)
            after = None

        else:
            after = Object(id=last_id)

        counted = 0

        async for message in channel.history(after=after, oldest_first=True, limit=None):
            if cls._count_up_now(message):
                counted += 1

        logger.debug(
            "[{}] Caught up {} messages for channel '{}' - ID: {}",
            NAME,
            counted,
            channel.name,
            channel.id,
        )

    @classmethod
    def get_counts(
        cls,
        guild_id: int,
        channel_id: int,
        from_ts: int,
        to_ts: int,
    ) -> List[Tuple[int, int]]:

        return cls.get_db(guild_id).get_record_range(channel_id, from_ts, to_ts)

    @classmethod
    def get_count_all(cls, guild_id: int, channel_id: int) -> int:
        """Returns all-time message count of given channel."""

        return cls.get_db(guild_id).get_count_all(channel_id)

    @classmethod
    def close(cls):
        for ch_id, db in cls._dbs.items():
            logger.debug("[{}] Closing database {}.", NAME, ch_id)
            db.close()

        # drop ref to prevent future unintended GC
        cls._dbs.clear()
        cls._pending.clear()


async def on_message_trigger(message: Message):

    try:
        if DataHandler.count_up(message):
            return

    except sqlite3.ProgrammingError:
        logger.exception("[{}] DB is closed, is this reloading?", NAME)

    except sqlite3.OperationalError:
        logger.exception("[{}] DB Operation failed", NAME)

    except AttributeError:
        logger.warning(
            "[{}] Got an invalid message from channel {}, ignoring.",
            NAME,
            getattr(message.channel, "id", None),
        )
    else:
        logger.debug(
            "[{}] Got a PM from {}, ignoring.", NAME, message.author.display_name
        )


async def get_message_count_total(context: Context, channel: TextChannel = None):
    """Reply with total message count of given channel, or current channel"""

    if context.guild is None:
        await context.reply("This command can only be used in a server.")
        return

    target = channel or context.channel
    total = DataHandler.get_count_all(context.guild.id, target.id)

    await context.reply(f"Total messages in {target.mention}: {total}")


# --- Interface ---


class ChatStatisticsCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        logger.info("[ChatStatisticsCog] starting")
        self.catch_up.start()

    def cog_unload(self):
        logger.info("[ChatStatisticsCog] stopping")
        self.catch_up.cancel()
        DataHandler.close()

    @tasks.loop(count=1)
    async def catch_up(self):
        await DataHandler.catch_up(self.bot)

    @catch_up.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()


__all__ = [
    CogRepresentation(ChatStatisticsCog),
    EventRepresentation(on_message_trigger, "on_message"),
    CommandRepresentation(
        get_message_count_total,
        name="msg_count",
        help="Shows all-time message count of this or given channel.", 
    ),
]
