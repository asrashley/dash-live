#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dashlive.server.options.dash_option import BoolDashOption
from dashlive.server.options.types import OptionUsage

from .http_error import VideoHttpError
from .video_corrupt import VideoCorruption, CorruptionFrameCount

VideoThumbnails = BoolDashOption(
    usage=OptionUsage.MANIFEST,
    short_name='vt',
    full_name='videoThumbnails',
    title='Video Thumbnails',
    description='Enable or disable thumbnail images for the video track',
    input_type='checkbox',
    cgi_name='thumbnails',
    cgi_choices=(
        ('No', '0'),
        ('Yes', '1')),
    featured=False)

video_options = [
    CorruptionFrameCount,
    VideoCorruption,
    VideoHttpError,
    VideoThumbnails,
]
