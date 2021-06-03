### Usage

```commandline
❯ py ./CustomizedMeow_py -h

usage: [-h] bot_token guild_id channel_id

positional arguments:
  bot_token   Bot's webhook url
  guild_id    Discord Server's ID
  channel_id  Discord Channel's ID where bot can talk to.

optional arguments:
  -h, --help  show this help message and exit
```

---

### Features

```
Meow World, Nyanstaree~🌟 I'm a playground bot, type /help for usage!

Commands:
  expansion   Shows/reload expansion commands.
  help        Shows this message
  latest      Shows latest uploaded video.
  py          Execute python code remotely.
  run         Run cyan run!
  streamgraph Get stream's public statistics graph. Due to check interval and...
  sysinfo     Get general system info. But why?

Type /help command for more info on a command.
You can also type /help category for more info on a category.
```

### Built-in

- `/expansion [action=list]`
  
  Shows/reload expansion commands. Without parameter or with parameter `list` will show loaded expansion status.

  With parameter `reload`, this will compare hash of expansion script and datafile to determine modified files.
  Then it tries to import it dynamically.
  
  You can add new commands or edit existing ones on-the-fly with this reload feature, as long as if it follows certain rules.
  
  Here's example what module should contain.
  
  ```python
  from discord.ext.commands import Context
  
  from . import CommandRepresentation
  
  
  async def some_command(context: Context):
      ...
  
  
  async def another_command(context: Context, some_args: str):
      ...
  
  
  __all__ = [
      CommandRepresentation(some_command, name="your_own_command", help="help_message"),
      CommandRepresentation(another_command, name="your_own_command", help="help_message")
  ]
  ```
  Any script containing `__all__` list with [`CommandRepresentaion`](BotComponents/__init__.py) class will be loaded dynamically upon reload call.

All other commands are not built-in. Documentation on those are currently WIP.
