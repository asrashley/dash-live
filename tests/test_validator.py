#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
from pathlib import Path
from typing import NotRequired, TypedDict
import unittest


from dashlive.mpeg.dash.validator.dash_element import DashElement
from dashlive.mpeg.dash.validator.options import ValidatorOptions
from dashlive.utils.date_time import to_iso_datetime

from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime

class OutputFilenameTestCase(TypedDict):
    filename: NotRequired[str]
    prefix: str
    elt_id: str
    bandwidth: int | None
    content_type: str
    expected: str

class TestValidator(FlaskTestBase):
    NOW = "2026-03-20T19:18:17Z"

    @MockTime(NOW)
    def test_output_filename(self) -> None:
        self.assertEqual(to_iso_datetime(datetime.datetime.now()), self.NOW)
        options = ValidatorOptions(
            dest=f'{self.app_folders.blob_folder / "dash_validator_test"}',
            prefix='test',
            start_time=datetime.datetime.now(),
        )
        url: str = 'https://example.cdn.test/video/abcdef/init.m4v'
        element = DashElement(options=options, elt=None, parent=None, url=url)
        dest_dir: Path = self.app_folders.blob_folder / "dash_validator_test" / self.NOW.replace(":", "-")
        test_cases: list[OutputFilenameTestCase] = [
            {'prefix': 'test', 'elt_id': 'id1', 'bandwidth': 1000, 'content_type': 'video',
             'expected': f'{dest_dir / "test_id1.m4v"}'},
            {'prefix': 'test', 'elt_id': None, 'bandwidth': 1000, 'content_type': 'video',
             'expected': f'{dest_dir / "test_1000.m4v"}'},
            {'prefix': None, 'elt_id': None, 'bandwidth': None, 'content_type': 'video',
             'expected': f'{dest_dir / "init.m4v"}'},
            {'prefix': None, 'elt_id': None, 'bandwidth': None, 'content_type': 'audio',
             'expected': f'{dest_dir / "init.m4a"}'},
            {'prefix': None, 'elt_id': None, 'bandwidth': None, 'content_type': 'text',
             'expected': f'{dest_dir / "init.mp4"}'},
            {'prefix': None, 'elt_id': None, 'bandwidth': 12345, 'content_type': 'image',
             'filename': 'https://example.cdn.test/thumbs/abcdef/thumb-456.jpg',
             'expected': f'{dest_dir / "thumb-456.jpg"}'},
            {'prefix': 'bbb', 'elt_id': 'one/two/three#4', 'bandwidth': None, 'content_type': 'video',
             'expected': f'{dest_dir / "bbb_one_two_three_4.m4v"}'},
            {'prefix': 'bbb', 'elt_id': 'one/two/#3', 'bandwidth': 12345, 'content_type': 'image',
             'filename': 'https://example.cdn.test/thumbs/abcdef/thumb-456.jpg',
             'expected': f'{dest_dir / "bbb_one_two_3.jpg"}'},
        ]
        for tc in test_cases:
            with self.subTest(**tc):
                expected: str = tc['expected']
                del tc['expected']
                filename: str = element.output_filename(
                    default='default.mp4', makedirs=False, **tc)
                self.assertEqual(filename, expected)


if __name__ == '__main__':
    unittest.main()
