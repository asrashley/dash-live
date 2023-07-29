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
from .dash_option import DashOption

VideoCorruption = DashOption(
    name='vcor',
    title='Video corruption',
    description=(
        'Cause video corruption to be generated when requesting a fragment at the given time. ' +
        'Invalid data is placed inside NAL packets of video frames. ' +
        'Each time must be in the form HH:MM:SSZ.'),
    cgi_name='vcorrupt',
    cgi_type='<time>,<time>,..',
    hidden=True,
    usage={'video'})

CorruptionFrameCount = DashOption(
    name='vcfc',
    title='Video corruption frame count',
    description=(
        'Number of frames to corrupt per segment. ' +
        'Only relevant when the corrupt CGI parameter is present.'),
    cgi_name='frames',
    cgi_type='<number>',
    usage={'video'})
