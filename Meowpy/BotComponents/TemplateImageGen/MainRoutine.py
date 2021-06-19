from io import BytesIO

from PIL import Image


def rotate_image(image: Image, angle: float) -> Image:
    return image.rotate(angle, expand=True)


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


def resize_image(image: Image, pixel_length) -> Image:
    """
    Only accepts squares.
    """

    return image.resize((pixel_length, pixel_length))


def main(bg_img_bytes: BytesIO, fore_img_bytes: BytesIO, angle, width, offset_x, offset_y):
    img = Image.open(fore_img_bytes)
    img.convert("RGBA")

    template = Image.open(bg_img_bytes)
    img.convert("RGBA")

    foreground = resize_image(rotate_image(make_square(img), angle), width)

    final_img = overlay_image(foreground, template, offset_x, offset_y)
    return final_img
