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

from dashlive.utils.fio import BitsFieldReader, BitsFieldWriter
from dashlive.utils.object_with_fields import ObjectWithFields

class BreakDuration(ObjectWithFields):
    @classmethod
    def parse(cls, src):
        kwargs = {}
        r = BitsFieldReader(cls, src, kwargs)
        r.read(1, 'auto_return')
        r.get(6, 'reserved')
        r.read(33, 'duration')
        return kwargs

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(1, 'auto_return')
        w.write(6, 'reserved', value=0x3F)
        w.write(33, 'duration')
