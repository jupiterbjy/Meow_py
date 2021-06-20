"""
Module to combine given image with template
"""

import pathlib
import json
from datetime import datetime
from io import BytesIO
from typing import Dict, Union, List

from PIL import Image
from discord.ext.commands import Context
from discord import Attachment, File
from loguru import logger

from .. import CommandRepresentation


ROOT = pathlib.Path(__file__).parent
config_path = ROOT.joinpath("config.json")
config: Dict[str, Union[str, int]] = json.loads(config_path.read_text())

angle: float
file_name: List[str] = []
bg_offset_after_rotate: List[int]
square_height: int

locals().update(config)

# prepare constants
BG_IMAGES = [BytesIO(ROOT.joinpath(fn).read_bytes()) for fn in file_name]
sandwich_mode = len(file_name) == 2


def rotate_image(image: Image, angle_: float) -> Image:
    return image.rotate(angle_, expand=True)


def overlay_image(image: Image, background_image: Image, offset_x, offset_y) -> Image:
    background_image.paste(image, (offset_x, offset_y), image)

    return background_image


def make_square(image: Image):
    width, height = image.size

    # check if already square
    if width == height:
        return image

    side = max(height, width)

    temp = Image.new(image.mode, (side, side))

    if width < height:
        temp.paste(image, ((side - width) // 2, 0), image)
    else:
        temp.paste(image, (0, (side - height) // 2), image)

    return temp


def pad(image: Image, margin: float):
    """
    Only accepts squares.
    """
    if not margin:
        return image

    width, _ = image.size
    pad_ = int(width * margin // 100)
    pad_half = pad_ // 2
    width += pad_

    temp = Image.new(image.mode, (width, width))
    temp.paste(image, (pad_half, pad_half), image)

    return temp


def resize_image(image: Image, pixel_length) -> Image:
    """
    Only accepts squares.
    """

    return image.resize((pixel_length, pixel_length))


def main(
    margin: float,
    bg_img_bytes: BytesIO,
    fore_img_bytes: BytesIO,
    background: bool,
    angle_,
    width,
    offset_x,
    offset_y,
):
    img = Image.open(fore_img_bytes).convert("RGBA")
    template = Image.open(bg_img_bytes).convert("RGBA")

    if not background:
        template = Image.new(template.mode, template.size)

    foreground = resize_image(
        pad(rotate_image(make_square(img), angle_), margin), width
    )

    return overlay_image(foreground, template, offset_x, offset_y)


def main_sandwiched(
    margin: float,
    bg_img_bytes: BytesIO,
    top_image_bytes: BytesIO,
    fore_img_bytes: BytesIO,
    background: bool,
    angle_,
    width,
    offset_x,
    offset_y,
):
    top_img = Image.open(top_image_bytes).convert("RGBA")

    temp_img = main(
        margin, bg_img_bytes, fore_img_bytes, background, angle_, width, offset_x, offset_y
    )
    final_img = overlay_image(top_img, temp_img, 0, 0)

    return final_img


async def gen_image(context: Context, margin_percent: float = 0.0, background: bool = True):
    username = context.author.display_name
    logger.info("Called from {}, param: {} {}", username, margin_percent, background)

    try:
        img: Attachment = context.message.attachments[0]
        data = BytesIO(await img.read())
    except IndexError:
        # no image, use user's profile image
        logger.debug("No image provided. Proceeding to use user's profile image.")

        data = BytesIO()

        await context.author.avatar_url.save(data)

    else:
        if "image" not in img.content_type:
            await context.reply("Received wrong file, send images only!")
            return

        logger.info("Image received from {}.", username)

    start_time = datetime.now()

    try:
        if sandwich_mode:
            output = main_sandwiched(
                margin_percent,
                BG_IMAGES[0],
                BG_IMAGES[1],
                data,
                background,
                angle,
                square_height,
                *bg_offset_after_rotate,
            )
        else:
            output = main(
                margin_percent,
                BG_IMAGES[0],
                data,
                background,
                angle,
                square_height,
                *bg_offset_after_rotate,
            )
    except Exception as err:
        text = f"Got {type(err).__name__}.\nDetail:\n```\n{err}\n```"

        await context.reply(text)
        logger.critical(text)

        raise

    time_took = datetime.now() - start_time

    output_bytes = BytesIO()
    output.save(output_bytes, format="PNG")
    output_bytes.seek(0)

    logger.info("Request for {} took {} microseconds.", username, time_took.microseconds)

    await context.reply(
        file=File(fp=output_bytes, filename=f"{context.message.id}.png")
    )


async def gen_image_error(context: Context, _):
    await context.reply("You passed wrong parameter! Check command `help template`")


__all__ = [
    CommandRepresentation(
        gen_image,
        name="template",
        help="Attach image to frame it, or user's profile image will be framed. Set margin in percent to add padding.",
        err_handler=gen_image_error
    )
]
