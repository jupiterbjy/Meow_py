"""
Module to combine given image with template
"""

import pathlib
import json
import functools
from datetime import datetime
from io import BytesIO
from typing import Dict, Union, List

from PIL import Image
from telegram.ext import CallbackContext, Filters, MessageHandler, CommandHandler
from telegram import Update, Document

from loguru import logger


MAX_ZOOM = -100
MAX_ZOOM_OUT = 1000

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
        rotate_image(pad(make_square(img), margin), angle_), width
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


def gen_image(update: Update, context: CallbackContext):

    logger.info("Called")

    args = context.args
    margin_percent: float = 0.0
    background: bool = True

    message = update.message
    user = message.from_user

    if args:
        try:
            margin_percent = float(args[0])
        except ValueError:
            pass

        try:
            background = bool(args[1])
        except (IndexError, ValueError):
            pass

    if not (MAX_ZOOM <= margin_percent <= MAX_ZOOM_OUT):
        message.reply_text(f"Margin is outside limit! Limit is [{MAX_ZOOM} ~ {MAX_ZOOM_OUT}]")
        return

    attachment = message.effective_attachment
    
    @functools.singledispatch
    def default(arg):
        logger.info("Using user's profile image")
        photo = user.get_profile_photos(limit=1).photos[0]
        return photo[-1].get_file()

    @default.register
    def _(arg: Document):
        logger.info("Using document, assuming image")
        return arg.get_file()
    
    @default.register
    def _(arg: list):
        logger.info("Using compressed image")
        return arg[0].get_file()

    try:
        image = default(attachment)
    except Exception as err:
        logger.critical(err)
        message.reply_text("Wrong file provided!")
        return
    
    username = user.name
    logger.info("Called from {}, param: {} {}", username, margin_percent, background)

    data = BytesIO(image.download_as_bytearray())

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

        message.reply_text(f"Got {type(err).__name__}.\nDetail:\n```\n{err}\n```")
        logger.critical(text)

        raise

    time_took = datetime.now() - start_time

    output_bytes = BytesIO()
    output.save(output_bytes, format="PNG")
    output_bytes.seek(0)

    logger.info("Request for {} took {} microseconds.", username, time_took.microseconds)

    message.reply_document(output_bytes, filename=f"{message.message_id}.png")


__all__ = [
    MessageHandler(Filters.caption(update=["/template"]), gen_image),
    CommandHandler("template", gen_image)
]
