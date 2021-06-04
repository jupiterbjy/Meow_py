"""
Dynamic module re-loader to load modules again.
"""

import pathlib
import importlib
from typing import List, Iterable
from loguru import logger

from BotComponents import CommandRepresentation


FOLDER_NAME = "BotComponents"
LOCATION = pathlib.Path(__file__).parent.joinpath(FOLDER_NAME)
LOADED_MODULE = {}
LOADED_LIST = {}
LOADED_FILE_HASH = {}


def load_command() -> List[CommandRepresentation]:
    """
    Dynamically loads command extensions in BotComponents.

    :return: List of CommandRepresentation
    """

    script_paths = fetch_scripts()

    # if no scripts then quickly return empty list
    if not script_paths:
        logger.info("No scripts to load.")
        return []

    # else invalidate cache and start loading.
    importlib.invalidate_caches()

    fetched_list = []

    for script_path in script_paths:

        try:
            # check if it's already loaded. if so, reload.
            if script_path.stem in LOADED_MODULE.keys():
                module = importlib.reload(LOADED_MODULE[script_path.stem])
            else:
                module = importlib.import_module(".".join((FOLDER_NAME, script_path.stem)))

        except SyntaxError as err:
            logger.critical("Got syntax error in {} at line {}, skipping", script_path.name, err.lineno)
            state = "Reason: SyntaxError"

        except Exception as err:
            logger.critical("Got {} while importing expansions\n\n{}", type(err).__name__, err)
            state = f"Reason: {type(err).__name__}"

        else:
            # update reference
            LOADED_MODULE[script_path.stem] = module

            # find if it also has data file with same name
            data = script_path.with_suffix(".json")

            if data.exists():
                hashed = hash(script_path.read_text() + data.read_text())
            else:
                hashed = hash(script_path.read_text())

            LOADED_FILE_HASH[script_path.stem] = hashed

            try:
                command_list = getattr(module, "__all__")
            except NameError:
                logger.critical("Missing name __all__ in global scope of the script {}, skipping.", script_path.name)
                state = "Reason: NameError"
            else:
                fetched_list.extend(command_list)
                state = ", ".join(str(command.name) for command in command_list)

        LOADED_LIST[f"{script_path.name}"] = state

    return fetched_list


def fetch_scripts() -> List[pathlib.Path]:
    """
    Dynamically search and load all scripts in BotComponents.

    THIS WILL NOT RELOAD __init__.py! This is limitation of importlib.

    :return: List[ScheduledTask]
    """

    logger.debug(f"Loader looking for scripts inside {LOCATION.as_posix()}")

    sources = [path_ for path_ in LOCATION.iterdir() if path_.suffix == ".py" and path_.stem != "__init__"]

    # check hash and only return non-existing/changed ones.
    def hash_validation_gen(paths: Iterable[pathlib.Path]):

        for path_ in paths:
            try:
                # find if it also has data file with same name
                data = path_.with_suffix(".json")

                if data.exists():
                    hashed = hash(path_.read_text() + data.read_text())
                else:
                    hashed = hash(path_.read_text())

                if LOADED_FILE_HASH[path_.stem] != hashed:
                    logger.debug("Got different hash on {}", path_.stem)
                    yield path_

            except KeyError:
                yield path_

    filtered = list(hash_validation_gen(sources))
    logger.debug(f"Found {len(filtered)} modified/new modules.")

    return filtered