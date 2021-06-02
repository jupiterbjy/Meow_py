"""
Setting this up everytime in interpreter ain't fun. So just import this in interpreter.
Will look for google api from file named `api_key` on cwd.
You can manually specify it when building resource file.

Readability is 'amazing', even I can't read well. Will add docstrings when I can.
"""

import pathlib
import datetime
from typing import Tuple

from dateutil.parser import isoparse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


assert HttpError
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"
API_FILE = pathlib.Path(__file__).parent.joinpath("api_key").absolute()


def build_youtube_resource(api_key=None):
    if api_key is None:
        # if file path is wrong, will raise file not found. handle it outside.
        with open(API_FILE) as _fp:
            api_key = _fp.read()

    youtube = build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, developerKey=api_key)
    return youtube


class VideoInfo:
    def __init__(self, dict_: dict):
        snippet = dict_["snippet"]

        self.title = snippet["title"]
        self.description = snippet["description"]
        self.channel_title = snippet["channelTitle"]

        self.published_at = snippet["publishedAt"]

        self.channel_id = snippet["channelId"]

        try:
            self.video_id = snippet["resourceId"]["videoId"]
        except KeyError:
            self.video_id = dict_["id"]

        try:
            self.live_content = snippet["liveBroadcastContent"]
        except KeyError:
            self.live_content = ""

        self._thumbnail = snippet["thumbnails"]

        is_stat_available = "statistics" in dict_.keys()

        self.view_count = dict_["statistics"]["viewCount"] if is_stat_available else 0
        self.like_count = dict_["statistics"]["likeCount"] if is_stat_available else 0

    @property
    def pub_date(self):
        return isoparse(self.published_at)

    @property
    def is_upcoming(self):
        return self.live_content == "upcoming"

    @property
    def is_live(self):
        return self.live_content == "live"

    def thumbnail_url(self, quality=2):
        quality = quality if 0 <= quality <= 4 else 4

        table = ("default", "medium", "high", "standard", "maxres")

        return self._thumbnail[table[quality]]["url"]


class GoogleClient:
    def __init__(self, api_key=None):
        self.youtube_client = build_youtube_resource(api_key)
        self.video_api = self.youtube_client.videos()
        self.channel_api = self.youtube_client.channels()
        self.search_api = self.youtube_client.search()
        self.playlist_item_api = self.youtube_client.playlistItems()

    def get_latest_videos(self, channel_id, fetch=3) -> Tuple[VideoInfo, ...]:
        # https://stackoverflow.com/a/55373181/10909029

        req = self.playlist_item_api.list(
            part="snippet,contentDetails",
            maxResults=fetch,
            playlistId="UU" + channel_id[2:]
        )

        return tuple(map(VideoInfo, req.execute()["items"]))

    def get_videos_info(self, *video_ids) -> Tuple[VideoInfo, ...]:

        req = self.video_api.list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids)
        )

        return tuple(map(VideoInfo, req.execute()["items"]))

    def get_stream_status(self, video_id) -> str:
        # This is most inefficient out of these methods.. but it's way simpler than first code.

        req = self.video_api.list(
            id=video_id, part="snippet", fields="items/snippet/liveBroadcastContent"
        )

        return req.execute()["items"][0]["snippet"]["liveBroadcastContent"]

    def get_video_title(self, video_id) -> str:

        req = self.video_api.list(
            id=video_id, part="snippet", fields="items/snippet/title"
        )

        return req.execute()["items"][0]["snippet"]["title"]

    def get_video_description(self, video_id) -> str:

        req = self.video_api.list(
            id=video_id, part="snippet", fields="items/snippet/description"
        )

        return req.execute()["items"][0]["snippet"]["description"]

    def get_channel_id(self, video_id) -> str:

        req = self.video_api.list(
            id=video_id, part="snippet", fields="items/snippet/channelId"
        )

        return req.execute()["items"][0]["snippet"]["channelId"]

    def get_subscribers_count(self, channel_id) -> int:

        req = self.channel_api.list(
            id=channel_id,
            part="statistics",
            fields="items/statistics/subscriberCount",
        )

        return req.execute()["items"][0]["statistics"]["subscriberCount"]

    def get_upcoming_streams(self, channel_id: str) -> Tuple[VideoInfo, ...]:

        req = self.search_api.list(
            channelId=channel_id, part="snippet", type="video", eventType="upcoming"
        )

        return tuple(vid_info for vid_info in map(VideoInfo, req.execute()["items"]) if vid_info.is_upcoming)

    def get_live_streams(self, channel_id: str) -> Tuple[VideoInfo, ...]:

        req = self.search_api.list(
            channelId=channel_id, part="snippet", type="video", eventType="live"
        )

        return tuple(vid_info for vid_info in map(VideoInfo, req.execute()["items"]) if vid_info.is_live)

    def get_start_time(self, video_id) -> datetime.datetime:

        req = self.video_api.list(
            id=video_id,
            part="liveStreamingDetails",
            fields="items/liveStreamingDetails/scheduledStartTime",
        )

        time_string = req.execute()["items"][0]["liveStreamingDetails"][
            "scheduledStartTime"
        ]

        start_time = isoparse(time_string)

        return start_time
