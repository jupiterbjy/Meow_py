from typing import Type

from loguru import logger

from discord.ext.commands import Bot, Cog


class RepresentationBase:
    name = ""

    def add(self, bot: Bot):
        """Put necessary steps to load module here"""
        raise NotImplementedError

    def unload(self, bot: Bot):
        """Put necessary steps to unload module here"""
        raise NotImplementedError


class CommandRepresentation(RepresentationBase):
    def __init__(self, func, *args, err_handler=None, **kwargs):
        self.name = kwargs["name"]
        self.func = func
        self.args = args
        self.kwargs = kwargs

        self.err_handler = err_handler

    def add(self, bot: Bot):

        logger.info("Adding {}", self.name)

        applied = bot.command(*self.args, **self.kwargs)(self.func)

        if self.err_handler:
            applied.error(self.err_handler)

    def unload(self, bot: Bot):

        logger.info("Unloading {}", self.name)

        bot.remove_command(self.name)


class CogRepresentation(RepresentationBase):
    def __init__(self, cog: Type[Cog], *_, **__):
        self.name = f"{cog.__name__}[Cog]"
        self.cog = cog

    def add(self, bot: Bot):

        logger.info("Adding {}", self.name)

        bot.add_cog(self.cog(bot))

    def unload(self, bot: Bot):

        logger.info("Unloading {}", self.name)

        try:
            bot.get_cog(self.cog.__name__).cog_unload()
        except AttributeError:
            pass

        bot.remove_cog(self.cog.__name__)


class EventRepresentation(RepresentationBase):

    def __init__(self, func, listen_name, *args, err_handler=None, **kwargs):
        self.name = f"{func.__name__}[Event]"
        self.func = func
        self.args = args
        self.kwargs = kwargs

        self.err_handler = err_handler
        self.listen_name = listen_name

    def add(self, bot: Bot):

        logger.info("Adding {}", self.name)

        bot.add_listener(self.func, self.listen_name)

        # Error handler is not tested at all, no guarantee it works.
        if self.err_handler:
            self.func.error(self.err_handler)

    def unload(self, bot: Bot):
        logger.info("Unloading {}", self.name)

        # need this mess to make reload work.
        if self.listen_name in bot.extra_events:

            for func in bot.extra_events[self.listen_name]:
                if func.__name__ == self.func.__name__:
                    bot.extra_events[self.listen_name].remove(func)
