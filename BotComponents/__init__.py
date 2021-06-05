from typing import Type

from loguru import logger

from discord.ext.commands import Bot, Cog


class CommandRepresentation:
    def __init__(self, func, *args, err_handler=None, **kwargs):
        self.name = kwargs["name"]
        self.func = func
        self.args = args
        self.kwargs = kwargs

        self.err_handler = err_handler

    def apply_command(self, bot: Bot):

        logger.info("Adding command {}", self.name)

        bot.remove_command(self.name)
        applied = bot.command(*self.args, **self.kwargs)(self.func)

        if self.err_handler:
            applied.error(self.err_handler)


class CogRepresentation:
    def __init__(self, cog: Type[Cog], *_, **__):
        self.name = f"{cog.__name__}[Cog]"
        self.cog = cog

    def apply_command(self, bot: Bot):

        logger.info("Adding cog {}", self.name)

        bot.remove_cog(self.cog.__name__)
        bot.add_cog(self.cog(bot))
