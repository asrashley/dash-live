#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .http_error import VideoHttpError
from .video_corrupt import VideoCorruption, CorruptionFrameCount

video_options = [
    CorruptionFrameCount,
    VideoCorruption,
    VideoHttpError
]
