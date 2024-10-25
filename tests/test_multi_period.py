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
import logging
from typing import ClassVar
import unittest

from dashlive.mpeg.dash.content_role import ContentRole

from .mixins.check_manifest import DashManifestCheckMixin
from .mixins.flask_base import FlaskTestBase, FixtureTrack, FixturePeriod
from .mixins.stream_fixtures import BBB_FIXTURE, TEARS_FIXTURE

class MultiPeriodTests(FlaskTestBase, DashManifestCheckMixin):
    periods: ClassVar[list[FixturePeriod]] = [
        FixturePeriod(pid="p1", fixture=BBB_FIXTURE, start=1, end=1,
                      tracks=[
                          FixtureTrack('video', 1, ContentRole.MAIN),
                          FixtureTrack('audio', 2, ContentRole.MAIN),
                      ]),
        FixturePeriod(pid="p2", fixture=TEARS_FIXTURE, start=4, end=6,
                      tracks=[
                          FixtureTrack('video', 1, ContentRole.MAIN),
                          FixtureTrack('audio', 2, ContentRole.MAIN),
                      ]),
    ]

    def test_generated_manifest_against_fixture_vod(self) -> None:
        self.setup_multi_period_stream(
            "testfix", "title", MultiPeriodTests.periods)
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='vod', acodec='mp4a', encrypted=False,
            now="2023-10-25T07:56:58Z", mps_name="testfix")

    def test_generated_manifest_against_fixture_live(self) -> None:
        self.setup_multi_period_stream(
            "testfix", "title", MultiPeriodTests.periods)
        self.check_generated_manifest_against_fixture(
            'hand_made.mpd', mode='live', acodec='mp4a', encrypted=False,
            now="2024-10-07T00:03:00Z", mps_name="testfix",
            start="2024-10-07T00:00:00Z")

    async def test_vod(self):
        self.setup_multi_period_stream("testfix", "title", MultiPeriodTests.periods)
        await self.check_a_manifest_using_major_options(
            filename='hand_made.mpd',
            mode='vod',
            mps_name="testfix",
            simplified=True)

    async def test_live(self):
        self.setup_multi_period_stream("livemps", "title", MultiPeriodTests.periods)
        await self.check_a_manifest_using_major_options(
            filename='hand_made.mpd',
            mode='live',
            mps_name="livemps",
            debug=False,
            simplified=True)


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
