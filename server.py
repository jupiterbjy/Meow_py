#!/usr/local/bin/python3.9

"""
Only tested to run on raspberry pi, but shouldn't be limited to it only.
"""

import asyncio
from datetime import timedelta

import daemon
from loguru import logger
from sys import executable


end_signature = "\u200a\u200a\u200a"
end_signature_encoded = end_signature.encode("utf8")


logger.add(
    "/home/pyexec/pyexec_{time}.log",
    level="DEBUG",
    rotation=timedelta(hours=3),
    retention="10 days",
    compression="zip",
)
# TODO: convert to versatile and reliable trio event loop, if connecting to asyncio is possible.


def encode(string: str):
    string += end_signature

    return string.encode("utf8")


def decode(byte_string: bytes):
    decoded = byte_string.decode("utf8")

    return decoded.removeprefix(end_signature)


async def try_to_send(writer, bytes_):
    try:
        writer.write(bytes_)
        await asyncio.wait_for(writer.drain(), 10)

    except Exception as err_:
        logger.critical("Could not send, reason: {}", err_)

    except asyncio.TimeoutError:
        logger.critical("Reached timeout while sending back. Is connection lost amid?")

    else:
        logger.info(f"Sent {len(bytes_)}")


async def receive(reader):
    data_ = b""

    while end_signature_encoded not in data_:
        data_ += await reader.read(1024)

    logger.info(f"Received {len(data_)}")

    return data_


async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger.debug("Receiving connection.")

    try:
        data = await receive(reader)
    except Exception as err_:
        logger.critical(err_)
        await try_to_send(writer, encode(str(err_)))
    else:

        decoded = decode(data).strip()

        logger.debug(decoded)

        proc = await asyncio.create_subprocess_exec(
            executable,
            "-c",
            decoded,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), 10)

        except asyncio.TimeoutError as err_:
            proc.kill()
            logger.critical(err_)
            await try_to_send(
                writer, encode("Reached 10 second timeout limit while executing.")
            )

        except Exception as err_:
            proc.kill()
            logger.critical(err_)
            await try_to_send(writer, encode(str(err_)))

        else:
            output = f"```\n{stdout.decode('utf8')}"

            if stderr:
                output += "\n" + stderr.decode("utf8")

            output += f"\n```\nReturn code was {proc.returncode}"

            await try_to_send(writer, encode(output))

    finally:

        writer.close()

        await writer.wait_closed()

        logger.debug("Connection closed.")


async def main_routine():
    server = await asyncio.start_server(handler, port=8123)

    address = server.sockets[0].getsockname()

    logger.info(f"Serving on {address}")

    async with server:
        await server.serve_forever()


def main():
    asyncio.run(main_routine())


with daemon.DaemonContext():
    main()
