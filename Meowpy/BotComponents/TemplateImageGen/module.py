"""
Module to combine given image with template
"""

import pathlib
import json
from io import BytesIO
from typing import Dict, Union, Tuple

from discord.ext.commands import Context
from discord import Attachment, File
from loguru import logger

from .. import CommandRepresentation
from . import MainRoutine


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict[str, Union[str, int]] = json.loads(config_path.read_text())

angle: float
file_name: str
bg_offset_after_rotate: Tuple[int, int]
square_height: int

locals().update(config)


# prepare constants
BG_IMAGE_BYTES = BytesIO(ROOT.joinpath(file_name).read_bytes())


async def gen_image(context: Context):
    logger.info("Called")

    try:
        img: Attachment = context.message.attachments[0]
    except IndexError:
        await context.reply("No images received!")
        return

    if "image" not in img.content_type:
        await context.reply("Received wrong file, send images only!")
        return

    try:
        data = BytesIO(await img.read())
        output = MainRoutine.main(BG_IMAGE_BYTES, data, angle, square_height, *bg_offset_after_rotate)
    except Exception as err:
        await context.reply(f"Got {type(err).__name__}. Detail:\n{err}")
        return

    output_bytes = BytesIO()
    output.save(output_bytes, format="PNG")
    output_bytes.seek(0)

    await context.reply(file=File(fp=output_bytes, filename=f"{context.message.id}.png"))


__all__ = [CommandRepresentation(gen_image, name="template", help="Receives image and combines with template.")]
