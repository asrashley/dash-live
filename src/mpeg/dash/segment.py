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

class Segment(object):
    def __init__(self, pos, size, duration=None):
        self.pos = pos
        self.size = size
        self.duration = duration

    def toJSON(self, pure=False):
        rv = {
            "pos": self.pos,
            "size": self.size,
        }
        if self.duration:
            rv["duration"] = self.duration
        return rv

    def __repr__(self):
        if self.duration:
            return '({:d},{:d},{:d})'.format(self.pos, self.size, self.duration)
        return '({:d},{:d})'.format(self.pos, self.size)