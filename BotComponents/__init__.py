from discord.ext.commands import Bot, CommandRegistrationError


class CommandRepresentation:
    def __init__(self, func, *args, err_handler=None, **kwargs):
        self.name = kwargs["name"]
        self.func = func
        self.args = args
        self.kwargs = kwargs

        self.err_handler = err_handler

    def apply_command(self, bot: Bot):

        try:
            applied = bot.command(*self.args, **self.kwargs)(self.func)

        except CommandRegistrationError:
            bot.remove_command(self.name)
            applied = bot.command(*self.args, **self.kwargs)(self.func)

        if self.err_handler:
            applied.error(self.err_handler)
