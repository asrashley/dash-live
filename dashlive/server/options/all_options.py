#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .audio_options import audio_options
from .dash_option import DashOption
from .drm_options import drm_options
from .event_options import event_options
from .manifest_options import manifest_options
from .player_options import player_options
from .text_options import text_options
from .video_options import video_options
from .utc_time_options import time_options

ALL_OPTIONS: list[DashOption] = (
    audio_options +
    drm_options +
    event_options +
    manifest_options +
    player_options +
    video_options +
    text_options +
    time_options)
