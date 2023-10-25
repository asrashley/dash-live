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
import datetime
import unittest

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase

class ManifestITest(FlaskTestBase, DashManifestCheckMixin):
    async def test_manifest_i_vod(self):
        await self.check_a_manifest_using_major_options('manifest_i.mpd', 'vod')

    @FlaskTestBase.mock_datetime_now(datetime.datetime.fromisoformat("2023-08-07T17:56:43Z"))
    async def test_manifest_i_live(self):
        await self.check_a_manifest_using_major_options('manifest_i.mpd', 'live')


if __name__ == '__main__':
    unittest.main()
