#!/usr/bin/python3

"""
Just a script using google Data API to fetch and accumulate live stream details.
Use `./log_stat -h` to see usages.

require google api key for this.
"""

import logging
import itertools
import pathlib
import datetime
import json
import argparse
from typing import Generator, Mapping, List, Union

import trio
import jsbeautifier

from log_initalizer import init_logger
from youtube_api_client import Client, HttpError
from plot_data import plot_main


ROOT = pathlib.Path(__file__).parent.absolute()
MAX_RETRY = 3


async def data_gen(record_sub=True) -> Generator[dict, None, None]:
    """
    Polls Google Data API periodically and yields it.

    :return: yields dict
    """
    sub_view_request = client.channel_api.list(
            id=client.get_channel_id(args.video_id),
            part="statistics",
            fields="items/statistics(subscriberCount)",
    )
    combined_request = client.video_api.list(
        id=args.video_id,
        part=["statistics", "liveStreamingDetails"],
        fields="items(statistics(likeCount,dislikeCount,viewCount),"
        "liveStreamingDetails/concurrentViewers)",
    )

    if record_sub:
        def request_join():
            dict_0 = sub_view_request.execute()["items"][0]["statistics"]
            response = combined_request.execute()["items"][0]

            for dict_ in response.values():
                dict_0.update(dict_)

            return dict_0
    else:
        def request_join():
            response = combined_request.execute()["items"][0]
            dict_0 = {}

            for dict_ in response.values():
                dict_0.update(dict_)

            return dict_0

    for _ in range(MAX_RETRY):
        try:
            for iteration in itertools.count(0):

                # These might be hidden in some streams.
                new_dict = {"viewCount": None, "likeCount": None, "dislikeCount": None}
                new_dict.update(request_join())

                log_string = (
                    "Viewers(Cur/Tot):{concurrentViewers}/{viewCount}"
                    " Likes:{likeCount}/{dislikeCount}".format(**new_dict)
                )

                logger.debug("[%s] %s", iteration, log_string)

                yield new_dict

                await trio.sleep(args.poll)

        except KeyError:
            logger.info("Stream closed.")
            continue

        except HttpError as err:
            logger.warning("HttpError: %s", err.error_details)
            continue

        except KeyboardInterrupt:
            logger.warning("Got ctrl+c")
            break

    # Block reached max retry
    else:
        logger.info("Max retry reached. Considering stream has ended.")


class Accumulator:
    """
    Just a storage only to provide __dict__
    as this use key of given dict as self.__dict__'s key, pep8 violation is inevitable.
    """

    def __init__(self):
        self.concurrentViewers = []
        self.viewCount = []
        self.likeCount = []
        self.dislikeCount = []
        self.subscriberCount = []

    def __len__(self):
        return len(self.concurrentViewers)

    def append(self, value_dict: Mapping):
        """
        Dumb dispatching to associated list

        :param value_dict: mapping containing keys with exact same name of object's attributes
        """

        for key, val in value_dict.items():
            self.__dict__[key].append(int(val) if val is not None else None)

    def dump(self) -> dict:
        """
        Just a convenience method, better than using dunder method directly!

        :return: object's __dict__
        """

        return self.__dict__


def write_json_closure(file_path: Union[str, pathlib.Path], data: Mapping):
    """
    Closure for initializing writing configs.
    Expects direct changes to data

    :param file_path: location to save file
    :param data: data to store - Anything that json serializable
    :return: function write(), no additional param needed
    """

    option_ = jsbeautifier.default_options()
    option_.indent_size = 2

    # validate path
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
    except OSError:
        logger.critical(
            "Could not touch the file at %s! Is filename supported by os?",
            file_path.as_posix(),
        )
        raise

    logger.debug("Successfully created %s.", file_path.as_posix())

    def write():
        with open(file_path, "w", encoding="utf8") as fp:
            fp.write(
                jsbeautifier.beautify(json.dumps(data, ensure_ascii=False), option_)
            )

        logger.info("Written %s sample(s).", len(data["data"]["dislikeCount"]))

    return write


def fetch_api(request) -> dict:
    """
    Just to shorten line width.

    :param request: google api request object ready to be executed
    :return: 1 step flatten and merged dict
    """

    response: Mapping[str, List[dict]] = request.execute()

    new_dict = {}

    for dict_ in response["items"]:
        new_dict.update(dict_)

    return new_dict


async def wait_for_stream(client_: Client, video_id):
    """
    Literally does what it's named for. await until designated stream time.

    Raises RuntimeError when stream is either seems to be canceled.
    """

    # check if actually it is active/upcoming stream

    # Dispatch cases
    status = client_.get_stream_status(video_id)

    if status == "live":
        logger.info(
            "API returned `%s`, stream already active.", status
        )
        return

    if status == "none":
        logger.critical(
            "API returned `%s`, is this a livestream?", status
        )
        raise RuntimeError("No upcoming/active stream.")

    # upcoming state, fetch scheduled start time
    start_time = client_.get_start_time(video_id)

    # get timedelta
    current = datetime.datetime.now(datetime.timezone.utc)

    # workaround for negative timedelta case. Checks if start time is future
    if start_time > current:

        delta = (start_time - current).seconds
        logger.info(
            "Will wait for %s seconds until stream starts. Press Ctrl+C to terminate.",
            delta,
        )

        # Sleep until due time
        await trio.sleep(delta)
        logger.info("Awake, waiting for live state.")

    # Check if stream is actually started
    while status := client_.get_stream_status(video_id):
        logger.debug("Status check: %s", status)

        if status == "none":
            logger.critical(
                "API returned `%s`, is stream canceled?", status
            )
            raise RuntimeError("No upcoming/active stream.")

        if status == "live":
            return

        await trio.sleep(5)


async def main():
    """
    Main coroutine
    """

    # validate api key and video ID
    try:
        video_title = client.get_video_title(args.video_id)

    except (HttpError, KeyError):
        logger.critical(
            "Request failed, check if API or video ID is valid, "
            "or if Data API Quota limit is reached. Check traceback for more detail."
        )
        raise

    # pre-bake file writer function. Will validate output path in process
    data = {"stream_title": video_title, "interval": args.poll}
    start_t = datetime.datetime.now()

    file_name = (
        f"{start_t.date().isoformat()}_{int(start_t.timestamp())}_{args.video_id}.json"
    )
    full_file_path: pathlib.Path = args.output.joinpath(pathlib.Path(file_name))

    write_func = write_json_closure(full_file_path, data)

    # initialize data dispatcher, and add __dict__ instance to data
    router_instance = Accumulator()
    data["data"] = router_instance.__dict__

    # to make async for loop do something every n time, will use infinite cycler.
    flush_interval_control = itertools.cycle(
        not bool(n) for n in reversed(range(args.flush))
    )

    # Wait for stream to start
    try:
        await wait_for_stream(client, args.video_id)
    except (Exception, KeyboardInterrupt):
        # Make sure to delete file
        logger.warning("Removing empty json file %s", full_file_path.as_posix())
        full_file_path.unlink()
        raise

    logger.info("Stream active, logging start.")

    # We got a lot of time for appending, hope async sleep in async for works better!
    try:
        async for fetched_dict in data_gen():
            router_instance.append(fetched_dict)

            if next(flush_interval_control):
                logger.info("Saving, do not interrupt.")
                write_func()

    except KeyboardInterrupt:
        logger.warning("Got ctrl+c")

    # hopefully this part should not run
    except Exception:
        logger.critical("Got unexpected exception. Saving file.")

        raise

    finally:
        # delete if 0 data is written
        if len(router_instance) == 0:
            logger.warning("Gathered data length is 0. Is connection stable?")
            logger.warning("Removing empty json file %s", full_file_path.as_posix())
            full_file_path.unlink()

        else:
            write_func()

            logger.info("Writing graph.")
            plot_main(data, full_file_path)


if __name__ == "__main__":

    # parsing start =================================

    parser = argparse.ArgumentParser(
        description="Records livestream details using Google Data API."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enables debug logging.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        type=pathlib.Path,
        default=ROOT.joinpath("Records"),
        help="Output folder. Default is script's directory.",
    )
    parser.add_argument(
        "-p",
        "--poll",
        metavar="INTERVAL",
        type=int,
        default=5,
        help="Changes interval between polls. Default is 5.",
    )
    parser.add_argument(
        "-a",
        "--api",
        metavar="KEY",
        type=str,
        default=None,
        help="Google Data API key, can be omitted if you "
             "store in file 'api_key' at script directory.",
    )
    parser.add_argument(
        "video_id", metavar="VIDEO_ID", type=str, help="ID of live youtube stream."
    )

    args = parser.parse_args()

    # parsing end ===================================

    logger = logging.getLogger(f"log_stat/{args.video_id}")

    client = Client(args.api)
    init_logger(logger, args.verbose)
    trio.run(main)
else:
    logger = logging.getLogger("log_stat")
    init_logger(logger, True)
