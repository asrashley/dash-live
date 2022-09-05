#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

supported_modes = {'live', 'vod', 'odvod'}

class CgiOption(object):
    """
    Container class for one CGI option
    """
    def __init__(self, name, title, options, hidden=False):
        """
        :name: The name of the options
        :title: The title to use in the UI
        :options: List of allowed values for this option
        """
        self.name = name
        self.title = title
        self.options = options
        self.hidden = hidden


options = [
    CgiOption(
        name='mode',
        title='Operating mode',
        options=[
            ('VOD live profile', 'mode=vod'),
            ('Live stream', 'mode=live'),
            ('VOD OD profile', 'mode=odvod'),
        ]
    ),
    CgiOption(
        name='abr',
        title='Adaptive bitrate',
        options=[
            ('yes', ''),
            ('no', 'abr=0'),
        ]
    ),
    CgiOption(
        name='acodec',
        title='Audio codec',
        options=[
            ('AAC', 'acodec=mp4a'),
            ('E-AC3', 'acodec=ec-3'),
            ('Both AAC and E-AC3', ''),
        ]
    ),
    CgiOption(
        name='drm',
        title='Encryption',
        options=[
            ('None', 'drm=none'),
            ('PlayReady', 'drm=playready'),
            ('Marlin', 'drm=marlin'),
            ('ClearKey', 'drm=clearkey'),
            ('All', 'drm=all'),
        ]
    ),
    CgiOption(
        name='drmloc',
        title='DRM location',
        options=[
            ('All locations', ''),
            ('mspr:pro element in MPD', 'drmloc=pro'),
            ('dash:cenc element in MPD', 'drmloc=cenc'),
            ('PSSH in init segment', 'drmloc=moov'),
            ('mspr:pro + dash:cenc in MPD', 'drmloc=pro-cenc'),
            ('mspr:pro MPD + PSSH init', 'drmloc=pro-moov'),
            ('dash:cenc MPD + PSSH init', 'drmloc=cenc-moov'),
        ]
    ),
    CgiOption(
        name='periods',
        title='Use multiple periods',
        options=[
            ('No', ''),
            ('2 periods', 'periods=2'),
            ('3 periods', 'periods=3'),
        ]
    ),
    CgiOption(
        name='events',
        title='DASH events',
        options=[
            ('None', ''),
            ('PingPong', 'events=ping'),
            ('SCTE35', 'events=scte35'),
        ]
    ),
    CgiOption(
        name='time',
        title='UTC timing element',
        options=[
            ('None', ''),
            ('xsd:date', 'time=xsd'),
            ('iso datetime', 'time=iso'),
            ('NTP', 'time=ntp'),
            ('HTTP HEAD', 'time=head'),
        ]
    ),
    CgiOption(
        name='mup',
        title='Manifest update rate',
        options=[
            ('Every 2 fragments', ''),
            ('Never', 'mup=-1'),
            ('Every fragment', 'mup=4'),
            ('Every 30 seconds', 'mup=30'),
        ],
        hidden=True
    ),
    CgiOption(
        name='base',
        title='BaseURL element',
        options=[
            ('Yes', ''),
            ('No', 'base=0'),
        ],
        hidden=True
    ),
    CgiOption(
        name='mse',
        title='Native playback',
        options=[
            ('Yes', ''),
            ('Use EME/MSE', 'mse=1'),
            ('Use EME/MSE (no DRM)', 'mse=2'),
        ]
    ),
]
