## Features

### Module based bot commands 

*Warning: `__init__.py` will never get reloaded due to limitation of `importlib.reload()` - leave it empty*

All Folders inside [`BotComponents`](/Meowpy/BotComponents) will be considered as module and will attempt to load `module.py` in it.
  
Inside `module.py`, script will look for `__all__` *list* containing any of following:
- CommandRepresentation
- CogRepresentation
- EventRepresentation

These are wrappers for corresponding discord.py's bot command / event listener / cog. 

Or if necessary, you can just leave `__all__` empty, module doesn't necessarily have to provide any feature.

Following is an example of `module.py`: 
```python
from discord.ext.commands import Cog, Context, Bot
from discord.ext import tasks
from discord import Message

from .. import CommandRepresentation, CogRepresentation, EventRepresentation


async def some_command(context: Context):
    pass


async def some_err_handler(context: Context, error):
    pass


async def another_command(context: Context, some_args: str):
    pass


async def very_event_much_wow(message: Message):
    pass


class SomeAwesomeCog(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.some_task.start()

    def cog_unload(self):
        """This will be called when reloading module, put cog cleanup here."""

    @tasks.loop(count=1)
    async def some_task(self):
        pass


__all__ = [
    # CommandRepresentation can have args/kwargs, these will be passed to `discord.ext.commands.Bot.commands()`.
    CommandRepresentation(some_command, name="command_name_a", help="RTFM", err_handler=some_err_handler),
    CommandRepresentation(another_command, name="command_name_b", help="some nice help message"),
    EventRepresentation(very_event_much_wow, "on_message"),
    CogRepresentation(SomeAwesomeCog),
]
```

Additionally, files in top level of each module folder will be hashed to determine whether there was change in file,
which then re-imported upon `//module reload` call by privileged user listed in [`configuration.json`](/Meowpy/configuration.json).

This means, if you use permanent data like database, you should nest it in a directory.

---

### Example Modules 

Below is structure of example modules in this repository.
```
├── BotComponents
│   ├── AutoAssign
│   │   ├── __init__.py
│   │   ├── config.json
│   │   └── module.py
│   │
│   ├── BasicCommands
│   │   ├── __init__.py
│   │   └── module.py
│   │
│   ├── CyanServerCommands
│   │   ├── __init__.py
│   │   ├── config.json
│   │   ├── module.py
│   │   └── youtube_api_client.py
│   │
│   ├── IntentionalErrorDemo
│   │   ├── __init__.py
│   │   └── module.py
│   │
│   ├── LinuxCommands
│   │   ├── __init__.py
│   │   └── module.py
│   │
│   ├── PythonExecution
│   │   ├── __init__.py
│   │   ├── config.json
│   │   └── module.py
│   │
│   ├── YtChatModule
│   │   ├── ChatOutputExample.json
│   │   ├── __init__.py
│   │   ├── config.json
│   │   └── module.py
│   │
│   └── __init__.py
│
└── configuration.json
```

For usage of each module, refer *Docstring* of each `module.py`.

Output of `//module` (some commands not shown):

![image](https://user-images.githubusercontent.com/26041217/122238394-0de29b80-cefb-11eb-891c-8012210f76b2.png)

Any failed to import modules will have red cross end of module folder's name.

---

Output of `//help` (some commands not shown):
```
Meow World, Nyanstaree~🌟 I'm a playground bot, type /help for usage!

​Commands:
  catchup     Manually triggers message catchup.
  countdown   Starts countdown, can't set longer than 10.
  echo        Echo back your writings.
  flushdb     Manually commit changes to db.
  help        Shows this message
  joined      Show your join dates. Pass Member ID to get that member's dates...
  latest      Shows latest uploaded video.
  module      Shows/reload dynamically loaded commands. Use parameter 'reload...
  py          Execute python code remotely.
  run         Run cyan run!
  stat        Shows your stats in this server.
  stickerinfo Shows debugging data of the sticker.
  streamgraph Get stream's public statistics graph. Due to check interval and...
  sysinfo     Get general system info. But why?

Type //help command for more info on a command.
You can also type //help category for more info on a category.
```
