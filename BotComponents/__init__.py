from typing import Type

from discord.ext.commands import Bot, Cog


class CommandRepresentation:
    def __init__(self, func, *args, err_handler=None, **kwargs):
        self.name = kwargs["name"]
        self.func = func
        self.args = args
        self.kwargs = kwargs

        self.err_handler = err_handler

    def apply_command(self, bot: Bot):

        bot.remove_command(self.name)
        applied = bot.command(*self.args, **self.kwargs)(self.func)

        if self.err_handler:
            applied.error(self.err_handler)


class CogRepresentation:
    def __init__(self, cog: Type[Cog], *_, **__):
        self.name = f"Cog {cog.__name__}"
        self.cog = cog

    def apply_command(self, bot: Bot):

        bot.remove_cog(self.cog.name)
        bot.add_cog(self.cog)
