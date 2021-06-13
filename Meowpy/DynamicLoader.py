"""
Dynamic module re-loader to load modules again.
"""

import pathlib
import importlib
from typing import List, Iterable, Tuple, Generator
from loguru import logger
from discord.ext.commands import Bot

from BotComponents import RepresentationBase


FOLDER_NAME = "BotComponents"
LOCATION = pathlib.Path(__file__).parent.joinpath(FOLDER_NAME)
LOADED_MODULE = {}
LOADED_LIST = {}
LOADED_FILE_HASH = {}


def load_command(bot: Bot) -> List[RepresentationBase]:
    """
    Dynamically loads extensions in BotComponents.

    :return: List of CommandRepresentation
    """

    script_hash_pairs = fetch_scripts()

    # if no scripts then quickly return empty list
    if not script_hash_pairs:
        logger.info("No scripts to load.")
        return []

    # else invalidate cache and start loading.
    importlib.invalidate_caches()

    fetched_list = []

    for script_path, hashed in script_hash_pairs:

        try:
            # check if it's already loaded. if so, reload.
            if script_path in LOADED_MODULE.keys():

                for representation in LOADED_MODULE[script_path].__all__:
                    representation: RepresentationBase
                    representation.unload(bot)

                module = importlib.reload(LOADED_MODULE[script_path])

            else:
                module = importlib.import_module(".".join((FOLDER_NAME, script_path.parent.stem, script_path.stem)))

        except SyntaxError as err:
            logger.critical("Got syntax error in {} at line {}, skipping", script_path.name, err.lineno)
            state = "Reason: SyntaxError"

        except Exception as err:
            logger.critical("Got {} while importing expansion {}\n{}", type(err).__name__, script_path.parent.name, err)
            state = f"Reason: {type(err).__name__}"

        else:
            # update reference
            LOADED_MODULE[script_path] = module
            LOADED_FILE_HASH[script_path] = hashed

            try:
                command_list = getattr(module, "__all__")
            except NameError:
                logger.critical("Missing name __all__ in global scope of the script {}, skipping.", script_path.name)
                state = "Reason: Missing __all__"
            else:
                fetched_list.extend(command_list)
                state = ", ".join(str(command.name) for command in command_list)

        LOADED_LIST[f"{script_path.parent.name}"] = state

    return fetched_list


def fetch_scripts() -> List[Tuple[pathlib.Path, int]]:
    """
    Dynamically search and load all scripts in BotComponents.

    THIS WILL NOT RELOAD __init__.py! This is limitation of importlib.

    :return: List[ScheduledTask]
    """

    logger.debug(f"Loader looking for scripts inside {LOCATION.as_posix()}")

    def path_gen():
        for path_ in (p for p in LOCATION.iterdir() if p.is_dir()):
            cur = path_.joinpath("module.py")
            if cur.exists():
                yield cur

    # check hash and only return non-existing/changed ones.
    def hash_validation_gen(paths: Iterable[pathlib.Path]) -> Generator[Tuple[pathlib.Path, int], None, None]:

        for path_ in paths:
            # find all file in top folder, this it NOT recursive.

            logger.debug("Checking module {}", path_)

            files = [p for p in path_.parent.iterdir() if p.is_file()]

            hashed = hash("".join(p.read_text() for p in files))

            try:
                if LOADED_FILE_HASH[path_] != hashed:
                    logger.debug("Got different hash on {}, marked for reloading.", path_.stem)

                    yield path_, hashed

            except KeyError:
                yield path_, hashed

    filtered = list(hash_validation_gen(path_gen()))
    logger.debug(f"Found {len(filtered)} modified/new modules.")

    return filtered
