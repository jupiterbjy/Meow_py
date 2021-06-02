#!/usr/local/bin/python3.9

"""
Only tested to run on raspberry pi, but shouldn't be limited to it only.
"""

import asyncio
from loguru import logger
from sys import executable


end_signature = "\u200a\u200a\u200a"
end_signature_encoded = end_signature.encode("utf8")


# logger.add("server_{time}", rotation="12:00", retention="10 days", compression="zip")


def encode(string: str):
    string += end_signature

    return string.encode("utf8")


def decode(byte_string: bytes):
    decoded = byte_string.decode("utf8")

    return decoded.removeprefix(end_signature)


async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

    logger.debug("Receiving connection.")

    data = b""

    while end_signature_encoded not in data:
        data += await reader.read(1024)

    logger.info(f"Received {len(data)}")

    decoded = decode(data).strip()

    logger.debug(decoded)

    try:
        proc = await asyncio.create_subprocess_exec(
            executable,
            "-c",
            decoded,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), 10)

    except asyncio.TimeoutError:
        send_byte = encode("Reached 10 second timeout limit while executing.")

    except Exception as err_:
        send_byte = encode(str(err_))

    else:
        output = f"```\n{stdout.decode('utf8')}"

        if stderr:
            output += "\n" + stderr.decode("utf8")

        output += f"\n```\nReturn code was {proc.returncode}"

        send_byte = encode(output)

    writer.write(send_byte)

    try:
        await asyncio.wait_for(writer.drain(), 10)
    except asyncio.TimeoutError:
        logger.critical("Reached timeout while sending back. Is connection lost amid?")
        writer.close()
        return

    logger.info(f"Sent {len(send_byte)}")

    writer.close()

    logger.debug("Connection closed.")


async def main_routine():
    server = await asyncio.start_server(handler, port=8123)

    addr = server.sockets[0].getsockname()

    logger.info(f"Serving on {addr}")

    async with server:
        await server.serve_forever()


while True:
    try:
        asyncio.run(main_routine())
    except Exception as err:
        pass
