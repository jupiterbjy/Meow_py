import pathlib
import asyncio
import json

from discord.ext.commands import Context
from discord import Embed, Colour
from loguru import logger

from . import CommandRepresentation


codec = "utf8"
end_signature = "\u200a\u200a\u200a"
end_signature_encoded = end_signature.encode(codec)

config_path = pathlib.Path(__file__).with_suffix(".json")
config = json.loads(config_path.read_text())


def encode(string: str):
    string += end_signature

    return string.encode(codec)


def decode(byte_string: bytes):
    decoded = byte_string.decode(codec)

    return decoded.removeprefix(end_signature)


async def receive_data(reader: asyncio.StreamReader) -> bytes:
    data = b""

    while end_signature_encoded not in data:
        data += await asyncio.wait_for(reader.read(1024), timeout=15)

    return data


async def run_script(context: Context, *, code: str):
    # Extract code
    striped = code.strip()

    if striped.startswith("```python"):
        code = striped.removeprefix("```python").removesuffix("```")

    else:
        await context.reply("Please use ```python\n<code>\n``` format!")

    logger.info(
        "Received code from {} by {}\ndetail: {}",
        context.channel,
        context.author,
        code,
    )

    if not config["ip"] or not config["port"]:
        await context.reply(
            "Sorry, My owner didn't provide me either IP or Port, I can't access server for execution!"
        )
        return

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(config["ip"], port=config["port"]), timeout=15)

    except asyncio.TimeoutError:
        await context.reply("Got timeout error connecting to server, this is probably my fault!")
        return

    except Exception as err_:
        logger.critical(err_)
        logger.critical(f"IP was {config['ip']}, and port was {config['port']}")

        await context.reply(
            f"Got {type(err_)} connecting to server, probably my fault!\n\n```{err_}```"
        )
        return

    # Send code
    send_byte = encode(code)

    try:
        writer.write(send_byte)
        await asyncio.wait_for(writer.drain(), 15)
    except asyncio.TimeoutError:
        await context.reply("Got timeout while sending execution results, probably my fault!")
        writer.close()

        return

    logger.info("Sent {}", len(send_byte))

    # read data until delim is received
    try:
        data = await receive_data(reader)

    except asyncio.TimeoutError:
        await context.reply("Got timeout while receiving execution results, probably my fault!")
        writer.close()

        return

    logger.debug("Got response, size {}", len(data))

    # decode and get return code
    resp = decode(data)

    # strip and get return cord
    lines = resp.split("\n")

    if "Return code" in lines[-1]:
        try:
            return_code = int(lines[-1].split()[-1])
        except ValueError:
            return_code = "No return code"

        resp = "\n".join(lines[:-1])
    else:
        return_code = "No return code"

    # prepare image and color
    image_url = config["image_success"] if not return_code else config["image_fail"]
    color = Colour.from_rgb(122, 196, 92) if not return_code else Colour.from_rgb(196, 92, 92)

    # prepare embed
    embed = Embed(title="Return code", description=str(return_code), colour=color)
    embed.set_thumbnail(url=image_url)

    await context.reply(resp, embed=embed)


__all__ = [CommandRepresentation(run_script, name="py", help="Execute python code remotely.")]
