### Usage

```commandline
usage: __main__.py [-h] [-p CONFIG_PATH]

optional arguments:
  -h, --help            show this help message and exit
  -p CONFIG_PATH, --config-path CONFIG_PATH
                        Path to configuration file. Default is
                        'configuration.json' in current script's path.
```

---

### Features

```
Meow World, Nyanstaree~🌟 I'm a playground bot, type /help for usage!

Commands:
  assignable  Show if user is applicable for assignation
  countdown   Starts countdown, can't set longer than 10.
  echo        Echo back your writings.
  help        Shows this message
  joined      Show your join dates. Pass Member ID to get that member's dates...
  latest      Shows latest uploaded video.
  module      Shows/reload dynamically loaded commands. Use parameter 'reload...
  py          Execute python code remotely.
  run         Run cyan run!
  streamgraph Get stream's public statistics graph. Due to check interval and...
  sub         Subscribe to live stream notification
  sysinfo     Get general system info. But why?
  unsub       Unsubscribe from live stream notification

Type /help command for more info on a command.
You can also type /help category for more info on a category.
```

### Built-in

- `/module [action=list]`
  
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
  Any script containing `__all__` list with [`CommandRepresentaion`](Meowpy/BotComponents/__init__.py) class will be loaded dynamically upon reload call.

All other commands are not built-in. Documentation on those are currently WIP.
