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
import unittest
from unittest.mock import ANY, call, patch

from dashlive.server import models
from dashlive.server.models.migrations.unique_track_ids import EnsureTrackIdsAreUnique

from .mixins.flask_base import FlaskTestBase

class DataMigrationTests(FlaskTestBase):
    def test_aac_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 1,
            "bbb_a1_enc": 1,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a1_04.mp4',
            'bbb_a1_enc_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_aac_audio_track_change_fails(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 1,
            "bbb_a1_enc": 1,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a1_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, False)

    def test_eac3_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a2_04.mp4',
            'bbb_a2_enc_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_text_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 3,
            "bbb_a2_enc": 3,
            "bbb_t1": 1,
        }
        new_files: list[str] = [
            'bbb_t1_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_no_tracks_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 3,
            "bbb_a2_enc": 3,
            "bbb_t1": 4,
        }
        new_files: list[str] = []
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def check_track_ids_are_unique(
            self,
            track_mapping: dict[str, int],
            new_files: list[str],
            success: bool) -> None:
        self.setup_media(with_subs=True)
        with self.app.app_context():
            for name in track_mapping.keys():
                media = models.MediaFile.get(name=name)
                self.assertIsNotNone(media)
                mrep = media.representation
                self.assertIsNotNone(
                    mrep,
                    msg=f'representation data missing from fixture {name}')
                mrep.track_id = track_mapping[name]
                media.track_id = track_mapping[name]
                media.set_representation(mrep)
            models.db.session.commit()
        blob_folder = self.FIXTURES_PATH.parent
        with self.app.app_context():
            session = models.db.session
            with patch('dashlive.server.models.MediaFile.modify_media_file') as mock_modify:
                mock_modify.return_value = success
                migration = EnsureTrackIdsAreUnique(blob_folder)
                # migration.log.info = lambda fmt, *args: print(fmt % args)
                # migration.log.debug = lambda fmt, *args: print(fmt % args)
                # migration.log.warning = lambda fmt, *args: print(fmt % args)
                errors: list[str] = []
                migration.log.errors = lambda fmt, *args: errors.append(fmt % args)
                migration.upgrade(session)
                if success:
                    self.assertListEqual(errors, [])
                calls: list[call] = [
                    call(session=session, blob_folder=blob_folder,
                         new_filename=(self.FIXTURES_PATH / name),
                         modify_atoms=ANY) for name in new_files]
                if not calls:
                    mock_modify.assert_not_called()
                else:
                    mock_modify.assert_has_calls(calls, any_order=True)


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    log = logging.getLogger('dashlive.server.models.migrations')
    log.setLevel(logging.DEBUG)
    unittest.main()
